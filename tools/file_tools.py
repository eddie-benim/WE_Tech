from __future__ import annotations

from pathlib import Path
from core.metadata_extractor import MetadataExtractor

_extractor = MetadataExtractor()


def read_file_text(file_path: str, max_chars: int = 8000) -> str:
    path = Path(file_path)
    if not path.exists():
        return f"File not found: {file_path}"
    text = _extractor.extract_text_sample(path, max_chars=max_chars)
    if not text.strip():
        return f"No extractable text found in {path.name}."
    return text


def list_reference_files(directory: str | None = None) -> list[dict]:
    import config
    base = Path(directory) if directory else config.COMPANY_FILES_DIR
    if not base.exists():
        return []
    files = [f for f in base.rglob("*") if f.is_file()]
    out = []
    for f in files:
        out.append({
            "name": f.name,
            "path": str(f),
            "extension": f.suffix.lower(),
            "size_kb": round(f.stat().st_size / 1024, 2),
        })
    return out


def extract_file_metadata(file_path: str) -> dict:
    from core.file_classifier import FileClassifier
    path = Path(file_path)
    if not path.exists():
        return {"error": f"File not found: {file_path}"}
    clf = FileClassifier()
    return clf.classify(path)


def get_reference_context(query: str, n_results: int = 8, vision_description: str = "") -> str:
    try:
        import config
        if not any(config.VECTOR_STORE_DIR.rglob("*")):
            return "No reference documents have been indexed yet."
        from core.vector_store import VectorStore
        vs = VectorStore()
        count = vs.count()
        if count == 0:
            return "No reference documents have been indexed yet."
        enriched_query = " ".join(filter(None, [query, vision_description[:400]]))
        results = vs.query(enriched_query, n_results=min(n_results, count))
        if not results:
            return "No relevant reference content found."
        parts = []
        for r in results:
            parts.append(f"[Source: {r['source']}]\n{r['text']}")
        return "\n\n---\n\n".join(parts)
    except Exception as e:
        return f"Vector store unavailable: {e}"


def find_similar_files(file_result: dict, n_results: int = 5) -> list[dict]:
    try:
        import config
        if not any(config.VECTOR_STORE_DIR.rglob("*")):
            return []
        from core.vector_store import VectorStore
        vs = VectorStore()
        if vs.meta_count() == 0:
            return []
        return vs.find_similar_files(file_result, n_results=n_results)
    except Exception as e:
        return []


def read_image_as_base64(file_path: str) -> str:
    import base64
    path = Path(file_path)
    if not path.exists():
        return ""
    return base64.b64encode(path.read_bytes()).decode("utf-8")
