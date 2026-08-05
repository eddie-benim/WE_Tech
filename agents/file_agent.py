from __future__ import annotations

import json
import os
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
    build_project_match_prompt,
)

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}
PDF_AS_IMAGE_EXTENSIONS = {".pdf"}


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

        try:
            from core.vector_store import VectorStore
            vs = VectorStore()
            has_vs = True
        except Exception:
            vs = None
            has_vs = False

        results = []
        for path in paths:
            self._log(f"Analysing: {path.name}")
            vision_description = ""
            try:
                result = self._analyze_single(path, naming_scheme, reference_files)
            except Exception as e:
                self._log(f"  Full AI analysis failed: {e}")
                self._log(f"  Attempting standalone vision before falling back...")
                ext = path.suffix.lower()
                if ext in IMAGE_EXTENSIONS or ext in PDF_AS_IMAGE_EXTENSIONS:
                    try:
                        api_key = os.environ.get("OPENAI_API_KEY") or config.OPENAI_API_KEY
                        vision_description = self._extractor.extract_vision_description(path, api_key=api_key)
                        self._log(f"  Standalone vision OK ({len(vision_description)} chars).")
                    except Exception as ve:
                        self._log(f"  Standalone vision also failed: {ve}")
                result = self._classifier.classify(path)
                result["original_path"] = str(path)
                result["confidence"] = "low"
                if vision_description:
                    result.setdefault("metadata", {})["vision_description"] = vision_description
                    parsed_meta = self._extractor.extract_metadata_from_vision(vision_description, path)
                    for k, v in parsed_meta.items():
                        if v and k != "vision_description":
                            result["metadata"].setdefault(k, v)

            if has_vs and vs:
                try:
                    similar = vs.find_similar_files(result, n_results=5)
                    result["similar_files"] = similar
                    if similar:
                        self._log(f"  Found {len(similar)} similar file(s) in database.")
                        match = self._match_project(result, similar)
                        result["project_match"] = match
                        if match.get("matched_project_number") and not result.get("metadata", {}).get("project_number"):
                            result.setdefault("metadata", {})["project_number"] = match["matched_project_number"]
                        self._log(f"  Project match: {match.get('matched_project_number', 'none')} ({match.get('matched_project_confidence', 'none')})")
                except Exception as e:
                    self._log(f"  Similarity search skipped: {e}")

            if has_vs and vs:
                try:
                    vs.store_file_metadata(result)
                    self._log(f"  Metadata stored in vector database.")
                except Exception as e:
                    self._log(f"  Could not store metadata: {e}")

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

        vision_description = ""
        specialist_results = {}
        is_visual = ext in IMAGE_EXTENSIONS or ext in PDF_AS_IMAGE_EXTENSIONS
        if is_visual:
            self._log(f"  Running vision analysis on {path.name}…")
            try:
                api_key = os.environ.get("OPENAI_API_KEY") or config.OPENAI_API_KEY
                vision_description = self._extractor.extract_vision_description(path, api_key=api_key)
                if vision_description:
                    self._log(f"  Vision analysis complete ({len(vision_description)} chars).")
                else:
                    self._log(f"  Vision analysis returned empty.")
            except Exception as e:
                self._log(f"  Vision analysis failed: {e}")

            if vision_description:
                try:
                    from agents.specialist_agents import SpecialistCoordinator
                    coord = SpecialistCoordinator(model=self.model)
                    doc_type_guess = rule_result.get("doc_type", "Unknown")
                    spec_output = coord.run(doc_type_guess, vision_description)
                    specialist_results = spec_output.get("specialist_results", {})
                    for log_line in spec_output.get("log", []):
                        self._log(f"  [specialist] {log_line}")
                except Exception as e:
                    self._log(f"  Specialist analysis failed: {e}")

        query_parts = [path.name, text_sample[:300], vision_description[:300]]
        query = " ".join(p for p in query_parts if p)
        reference_context = get_reference_context(query, n_results=5)

        user_prompt = build_file_analysis_prompt(
            filename=path.name,
            extension=ext,
            text_sample=text_sample,
            rule_based_result=rule_result,
            naming_scheme=naming_scheme,
            reference_context=reference_context,
            vision_description=vision_description,
        )

        ai_result = self._chat_json(
            system=FILE_SYSTEM_PROMPT,
            user=user_prompt,
            max_tokens=1500,
        )

        if ai_result.get("parse_error"):
            self._log(f"  JSON parse failed for {path.name}, using rule-based result.")
            base = {**rule_result, "size_kb": size_kb, "original_path": str(path)}
            if vision_description:
                base.setdefault("metadata", {})["vision_description"] = vision_description
            return base

        metadata = ai_result.get("metadata", rule_result.get("metadata", {}))
        if vision_description and not metadata.get("vision_description"):
            metadata["vision_description"] = vision_description
        if specialist_results:
            metadata["specialist_analysis"] = specialist_results

        return {
            "original_name": path.name,
            "original_path": str(path),
            "suggested_name": ai_result.get("suggested_name", rule_result.get("suggested_name", path.name)),
            "doc_type": ai_result.get("doc_type", rule_result.get("doc_type", "Unknown")),
            "format": ai_result.get("format", fmt),
            "extension": ext,
            "size_kb": size_kb,
            "metadata": metadata,
            "confidence": ai_result.get("confidence", "low"),
        }

    def _match_project(self, file_result: dict, similar_files: list[dict]) -> dict:
        if not similar_files:
            return {"matched_project_number": None, "matched_project_confidence": "none", "reasoning": "No similar files found."}

        top = similar_files[0]
        if top.get("similarity", 0) >= 0.85 and top.get("project_number"):
            return {
                "matched_project_number": top["project_number"],
                "matched_project_confidence": "high",
                "reasoning": f"High similarity ({top['similarity']:.2f}) to {top['filename']}",
                "recommended_folder": top.get("organised_path", ""),
            }

        prompt = build_project_match_prompt(file_result, similar_files)
        match = self._chat_json(
            system=FILE_SYSTEM_PROMPT,
            user=prompt,
            max_tokens=300,
        )
        if match.get("parse_error"):
            return {"matched_project_number": None, "matched_project_confidence": "none", "reasoning": "Model could not determine a match."}
        return match

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
