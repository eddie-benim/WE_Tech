from __future__ import annotations

import json
from pathlib import Path

import config
from agents.base_agent import BaseAgent
from core.file_classifier import FileClassifier
from core.metadata_extractor import MetadataExtractor
from tools.file_tools import get_reference_context, list_reference_files
from tools.naming_tools import propose_naming_scheme
from prompts.file_prompts import (
    FILE_SYSTEM_PROMPT,
    build_file_analysis_prompt,
    build_naming_scheme_prompt,
)


class FileAgent(BaseAgent):

    def __init__(self, model: str | None = None):
        super().__init__(model)
        self._classifier = FileClassifier()
        self._extractor = MetadataExtractor()

    def analyze_files(self, paths: list[Path]) -> list[dict]:
        self.log = []
        self._log(f"Starting analysis of {len(paths)} file(s).")

        reference_files = list_reference_files()
        naming_scheme = self._infer_naming_scheme(reference_files)
        self._log(f"Naming scheme inferred: {naming_scheme.get('scheme', '—')}")

        results = []
        for path in paths:
            self._log(f"Analysing: {path.name}")
            result = self._analyze_single(path, naming_scheme, reference_files)
            results.append(result)
            self._log(f"  → {result.get('doc_type', 'Unknown')} | {result.get('suggested_name', path.name)}")

        self._log("Analysis complete.")
        return results

    def _analyze_single(self, path: Path, naming_scheme: dict, reference_files: list[dict]) -> dict:
        ext = path.suffix.lower()
        fmt = config.SUPPORTED_EXTENSIONS.get(ext, ext.upper().lstrip("."))
        size_kb = round(path.stat().st_size / 1024, 2)

        rule_result = self._classifier.classify(path)

        text_sample = self._extractor.extract_text_sample(path, max_chars=3000)

        query = f"{path.name} {text_sample[:300]}"
        reference_context = get_reference_context(query, n_results=5)

        user_prompt = build_file_analysis_prompt(
            filename=path.name,
            extension=ext,
            text_sample=text_sample,
            rule_based_result=rule_result,
            naming_scheme=naming_scheme,
            reference_context=reference_context,
        )

        ai_result = self._chat_json(
            system=FILE_SYSTEM_PROMPT,
            user=user_prompt,
            max_tokens=1000,
        )

        if ai_result.get("parse_error"):
            self._log(f"  JSON parse failed for {path.name}, using rule-based result.")
            return {**rule_result, "size_kb": size_kb, "original_path": str(path)}

        return {
            "original_name": path.name,
            "original_path": str(path),
            "suggested_name": ai_result.get("suggested_name", rule_result.get("suggested_name", path.name)),
            "doc_type": ai_result.get("doc_type", rule_result.get("doc_type", "Unknown")),
            "format": ai_result.get("format", fmt),
            "extension": ext,
            "size_kb": size_kb,
            "metadata": ai_result.get("metadata", rule_result.get("metadata", {})),
            "confidence": ai_result.get("confidence", "low"),
        }

    def _infer_naming_scheme(self, reference_files: list[dict]) -> dict:
        if not reference_files:
            return {
                "scheme": "PROJECT-NUMBER_DOC-TYPE_DESCRIPTION_REVISION",
                "example": "PRJ-001_PFD_Separation-Train_Rev0.pdf",
                "separator": "_",
                "confidence": "default",
            }

        rule_based = propose_naming_scheme(reference_files)

        if len(reference_files) >= 5:
            self._log("Enough reference files found — asking model to refine naming scheme.")
            ai_scheme = self._chat_json(
                system=FILE_SYSTEM_PROMPT,
                user=build_naming_scheme_prompt(reference_files),
                max_tokens=400,
            )
            if not ai_scheme.get("parse_error"):
                return ai_scheme

        return rule_based