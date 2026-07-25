from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import chromadb
from chromadb.utils import embedding_functions

import config
from core.metadata_extractor import MetadataExtractor


class VectorStore:

    def __init__(self):
        api_key = os.environ.get("OPENAI_API_KEY") or config.OPENAI_API_KEY
        self._client = chromadb.PersistentClient(path=str(config.VECTOR_STORE_DIR))
        self._ef = embedding_functions.OpenAIEmbeddingFunction(
            api_key=api_key,
            model_name=config.EMBEDDING_MODEL,
        )
        self._collection = self._client.get_or_create_collection(
            name=config.CHROMA_COLLECTION_COMPANY,
            embedding_function=self._ef,
        )
        self._meta_collection = self._client.get_or_create_collection(
            name=config.CHROMA_COLLECTION_METADATA,
            embedding_function=self._ef,
        )
        self._extractor = MetadataExtractor()

    def index_directory(self, directory: Path) -> dict:
        files = [f for f in directory.rglob("*") if f.is_file()]
        total_chunks = 0
        indexed_files = 0

        for fpath in files:
            text = self._extractor.extract_text_sample(fpath, max_chars=50000)
            if not text.strip():
                continue
            chunks = self._chunk(text)
            if not chunks:
                continue
            ids = [self._chunk_id(fpath, i) for i in range(len(chunks))]
            metas = [{"source": fpath.name, "chunk": i} for i in range(len(chunks))]
            self._collection.upsert(documents=chunks, ids=ids, metadatas=metas)
            total_chunks += len(chunks)
            indexed_files += 1

        return {"files": indexed_files, "indexed": total_chunks}

    def store_file_metadata(self, file_result: dict):
        filename = file_result.get("original_name", "unknown")
        meta = file_result.get("metadata", {})
        doc_type = file_result.get("doc_type", "Unknown")
        vision_desc = meta.get("vision_description", "")
        unit_ops = meta.get("unit_operations", [])
        instruments = meta.get("instrumentation", [])
        project_num = meta.get("project_number", "")

        embedding_text = " ".join(filter(None, [
            doc_type,
            project_num,
            meta.get("client", ""),
            meta.get("description", ""),
            " ".join(unit_ops) if isinstance(unit_ops, list) else "",
            " ".join(instruments) if isinstance(instruments, list) else "",
            vision_desc[:1000] if vision_desc else "",
        ]))

        if not embedding_text.strip():
            return

        doc_id = hashlib.md5(filename.encode()).hexdigest()

        storable_meta = {
            "filename": filename,
            "doc_type": doc_type,
            "project_number": project_num,
            "suggested_name": file_result.get("suggested_name", filename),
            "original_path": file_result.get("original_path", ""),
            "organised_path": file_result.get("organised_path", ""),
            "unit_operations": json.dumps(unit_ops) if isinstance(unit_ops, list) else str(unit_ops),
            "instrumentation": json.dumps(instruments[:20]) if isinstance(instruments, list) else "",
            "client": meta.get("client", ""),
            "revision": meta.get("revision", ""),
        }

        self._meta_collection.upsert(
            documents=[embedding_text],
            ids=[doc_id],
            metadatas=[storable_meta],
        )

    def find_similar_files(self, file_result: dict, n_results: int = 5) -> list[dict]:
        meta = file_result.get("metadata", {})
        doc_type = file_result.get("doc_type", "")
        unit_ops = meta.get("unit_operations", [])
        instruments = meta.get("instrumentation", [])
        vision_desc = meta.get("vision_description", "")

        query_text = " ".join(filter(None, [
            doc_type,
            " ".join(unit_ops) if isinstance(unit_ops, list) else "",
            " ".join(instruments[:10]) if isinstance(instruments, list) else "",
            vision_desc[:500] if vision_desc else "",
        ]))

        if not query_text.strip() or self._meta_collection.count() == 0:
            return []

        results = self._meta_collection.query(
            query_texts=[query_text],
            n_results=min(n_results, self._meta_collection.count()),
        )

        output = []
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        for doc, m, dist in zip(docs, metas, distances):
            similarity = round(1 - dist, 3) if dist <= 1 else 0.0
            output.append({
                "filename": m.get("filename", ""),
                "doc_type": m.get("doc_type", ""),
                "project_number": m.get("project_number", ""),
                "suggested_name": m.get("suggested_name", ""),
                "organised_path": m.get("organised_path", ""),
                "unit_operations": json.loads(m.get("unit_operations", "[]")),
                "similarity": similarity,
            })

        return output

    def query(self, text: str, n_results: int = None) -> list[dict]:
        n = n_results or config.TOP_K_RETRIEVAL
        count = self._collection.count()
        if count == 0:
            return []
        results = self._collection.query(
            query_texts=[text],
            n_results=min(n, count),
        )
        output = []
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        for doc, meta in zip(docs, metas):
            output.append({"text": doc, "source": meta.get("source", ""), "chunk": meta.get("chunk", 0)})
        return output

    def count(self) -> int:
        return self._collection.count()

    def meta_count(self) -> int:
        return self._meta_collection.count()

    def _chunk(self, text: str) -> list[str]:
        size = config.CHUNK_SIZE
        overlap = config.CHUNK_OVERLAP
        chunks = []
        start = 0
        while start < len(text):
            end = start + size
            chunks.append(text[start:end])
            start += size - overlap
        return chunks

    def _chunk_id(self, path: Path, index: int) -> str:
        raw = f"{path.name}::{index}"
        return hashlib.md5(raw.encode()).hexdigest()
