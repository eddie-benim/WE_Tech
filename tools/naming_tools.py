from __future__ import annotations

import re
from pathlib import Path

import config

def generate_filename(
    doc_type: str,
    project_number: str = "",
    description: str = "",
    revision: str = "",
    extension: str = ".pdf",
) -> str:
    sep = config.NAMING_SEPARATOR
    parts = []

    if project_number:
        parts.append(sanitize(project_number))

    type_token = _type_token(doc_type)
    if type_token:
        parts.append(type_token)

    if description:
        parts.append(sanitize(description))

    parts.append(sanitize(revision or config.DEFAULT_REVISION))

    raw = sep.join(p for p in parts if p)
    if len(raw) > config.MAX_FILENAME_LENGTH:
        raw = raw[: config.MAX_FILENAME_LENGTH]

    ext = extension if extension.startswith(".") else f".{extension}"
    return raw + ext.lower()


def propose_naming_scheme(reference_files: list[dict]) -> dict:
    patterns: dict[str, int] = {}
    for f in reference_files:
        name = f.get("name", "")
        pattern = _infer_pattern(name)
        patterns[pattern] = patterns.get(pattern, 0) + 1

    if not patterns:
        return {
            "scheme": "PROJECT-NUMBER_DOC-TYPE_DESCRIPTION_REVISION",
            "example": "PRJ-001_PFD_Separation-Train_Rev0.pdf",
            "separator": "_",
            "confidence": "default",
        }

    best = max(patterns, key=patterns.get)
    return {
        "scheme": best,
        "example": _scheme_example(best),
        "separator": _detect_separator(reference_files),
        "confidence": "inferred" if patterns[best] > 1 else "low",
        "sample_count": patterns[best],
    }


def sanitize(text: str) -> str:
    text = re.sub(r"[^\w\s\-]", "", text)
    text = re.sub(r"[\s]+", "-", text.strip())
    return text


def build_folder_path(
    output_root: Path,
    project_number: str = "",
    client: str = "",
    doc_type: str = "",
) -> Path:
    if project_number:
        project_folder = sanitize(project_number)
    elif client:
        project_folder = sanitize(client)
    else:
        project_folder = "Unassigned"

    type_folder = sanitize(doc_type) if doc_type else "Unsorted"
    return output_root / project_folder / type_folder


def _type_token(doc_type: str) -> str:
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
        "Unknown": "DOC",
    }
    return mapping.get(doc_type, "DOC")


def _infer_pattern(filename: str) -> str:
    stem = Path(filename).stem
    parts = re.split(r"[_\-\s]+", stem)
    pattern_parts = []
    for part in parts:
        if re.match(r"^(PRJ|P)[-_]?\d+", part, re.IGNORECASE):
            pattern_parts.append("PROJECT-NUMBER")
        elif re.match(r"^(Rev|R)\w*", part, re.IGNORECASE):
            pattern_parts.append("REVISION")
        elif part.upper() in ("PFD", "PID", "HEB", "EQSZ", "PROP", "DS", "ISO", "GA", "CE", "HAZOP", "RPT", "DOC"):
            pattern_parts.append("DOC-TYPE")
        else:
            pattern_parts.append("DESCRIPTION")
    deduped = []
    for p in pattern_parts:
        if not deduped or deduped[-1] != p:
            deduped.append(p)
    return "_".join(deduped) if deduped else "DESCRIPTION"


def _detect_separator(files: list[dict]) -> str:
    underscore = sum(1 for f in files if "_" in f.get("name", ""))
    hyphen = sum(1 for f in files if "-" in f.get("name", ""))
    return "_" if underscore >= hyphen else "-"


def _scheme_example(scheme: str) -> str:
    replacements = {
        "PROJECT-NUMBER": "PRJ-042",
        "DOC-TYPE": "PFD",
        "DESCRIPTION": "Separation-Train",
        "REVISION": "Rev0",
    }
    result = scheme
    for k, v in replacements.items():
        result = result.replace(k, v)
    return result + ".pdf"