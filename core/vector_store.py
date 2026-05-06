from __future__ import annotations

import hashlib
from pathlib import Path

import chromadb
from chromadb.utils import embedding_functions

import config
from core.metadata_extractor import MetadataExtractor


class VectorStore:

    def __init__(self):
        self._client = chromadb.PersistentClient(path=str(config.VECTOR_STORE_DIR))
        self._ef = embedding_functions.OpenAIEmbeddingFunction(
            api_key=config.OPENAI_API_KEY,
            model_name=config.EMBEDDING_MODEL,
        )
        self._collection = self._client.get_or_create_collection(
            name=config.CHROMA_COLLECTION_COMPANY,
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

    def query(self, text: str, n_results: int = None) -> list[dict]:
        n = n_results or config.TOP_K_RETRIEVAL
        results = self._collection.query(
            query_texts=[text],
            n_results=min(n, self._collection.count() or 1),
        )
        output = []
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        for doc, meta in zip(docs, metas):
            output.append({"text": doc, "source": meta.get("source", ""), "chunk": meta.get("chunk", 0)})
        return output

    def count(self) -> int:
        return self._collection.count()

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