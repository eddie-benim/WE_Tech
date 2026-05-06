from __future__ import annotations

import re
from pathlib import Path

import config
from core.metadata_extractor import MetadataExtractor

class FileClassifier:

    def __init__(self):
        self._extractor = MetadataExtractor()

    def classify(self, path: Path) -> dict:
        ext = path.suffix.lower()
        fmt = config.SUPPORTED_EXTENSIONS.get(ext, ext.upper().lstrip("."))
        size_kb = path.stat().st_size / 1024

        text_sample = self._extractor.extract_text_sample(path, max_chars=2000)
        doc_type = self._detect_type(path.name, text_sample)
        metadata = self._extractor.extract_metadata(path, text_sample, doc_type)
        suggested_name = self._suggest_name(path, doc_type, metadata)

        return {
            "original_name": path.name,
            "original_path": str(path),
            "suggested_name": suggested_name,
            "doc_type": doc_type,
            "format": fmt,
            "extension": ext,
            "size_kb": round(size_kb, 2),
            "metadata": metadata,
        }

    def _detect_type(self, filename: str, text_sample: str) -> str:
        combined = (filename + " " + text_sample).lower()
        for doc_type, keywords in config.FILE_TYPE_KEYWORDS.items():
            for kw in keywords:
                if kw.lower() in combined:
                    return doc_type
        return "Unknown"

    def _suggest_name(self, path: Path, doc_type: str, metadata: dict) -> str:
        sep = config.NAMING_SEPARATOR
        parts = []

        project_num = metadata.get("project_number", "")
        if project_num:
            parts.append(self._sanitize(project_num))

        type_token = self._type_token(doc_type)
        if type_token:
            parts.append(type_token)

        description = metadata.get("description", "")
        if description:
            parts.append(self._sanitize(description))

        revision = metadata.get("revision") or config.DEFAULT_REVISION
        parts.append(revision)

        if not parts:
            parts.append(self._sanitize(path.stem))

        raw = sep.join(p for p in parts if p)
        if len(raw) > config.MAX_FILENAME_LENGTH:
            raw = raw[: config.MAX_FILENAME_LENGTH]

        return raw + path.suffix.lower()

    def _type_token(self, doc_type: str) -> str:
        mapping = {
            "PFD": "PFD",
            "P&ID": "PID",
            "Heat & Energy Balance": "HEB",
            "Equipment Sizing": "EQSZ",
            "Proposal": "PROP",
            "Data Sheet": "DS",
            "Isometric": "ISO",
            "GA Drawing": "GA",
            "Cause & Effect": "CE",
            "Hazop": "HAZOP",
            "Report": "RPT",
        }
        return mapping.get(doc_type, "DOC")

    def _sanitize(self, text: str) -> str:
        text = re.sub(r"[^\w\s\-]", "", text)
        text = re.sub(r"[\s]+", "-", text.strip())
        return text