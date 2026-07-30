from __future__ import annotations

import json
from pathlib import Path

import config
from agents.base_agent import BaseAgent
from prompts.query_prompts import (
    QUERY_SYSTEM_PROMPT,
    build_intent_extraction_prompt,
    build_retrieval_response_prompt,
)


class QueryAgent(BaseAgent):

    def run(self, user_query: str) -> dict:
        self.log = []
        self._log(f"Query received: {user_query}")

        self._log("Extracting search intent…")
        intent = self._extract_intent(user_query)
        self._log(f"Intent: project={intent.get('project_number')} | types={intent.get('doc_types')} | context={intent.get('process_context')}")

        project_files = []
        project_number = intent.get("project_number")
        if project_number:
            self._log(f"Searching metadata store for project {project_number}…")
            project_files = self._search_by_project(project_number, intent.get("doc_types", []))
            self._log(f"Found {len(project_files)} file(s) in project {project_number}.")

        self._log("Running semantic similarity search…")
        query_text = self._build_semantic_query(intent)
        similar_files = self._semantic_search(query_text, n_results=8)
        self._log(f"Found {len(similar_files)} semantically similar file(s).")

        if project_number:
            similar_files = [
                f for f in similar_files
                if f.get("project_number", "").upper() != project_number.upper()
            ]

        self._log("Generating response…")
        response_text = self._chat(
            system=QUERY_SYSTEM_PROMPT,
            user=build_retrieval_response_prompt(
                user_query=user_query,
                intent=intent,
                file_results=similar_files,
                project_files=project_files,
            ),
            max_tokens=1200,
        )

        self._log("Done.")

        return {
            "response": response_text,
            "intent": intent,
            "project_files": project_files,
            "similar_files": similar_files,
            "log": self.log,
        }

    def _extract_intent(self, query: str) -> dict:
        result = self._chat_json(
            system=QUERY_SYSTEM_PROMPT,
            user=build_intent_extraction_prompt(query),
            max_tokens=400,
        )
        if result.get("parse_error"):
            return {
                "project_number": None,
                "doc_types": [],
                "process_context": query,
                "unit_operations": [],
                "action_context": "",
                "similarity_needed": True,
                "keywords": [],
            }
        return result

    def _search_by_project(self, project_number: str, doc_types: list[str]) -> list[dict]:
        try:
            from core.vector_store import VectorStore
            vs = VectorStore()
            if vs.meta_count() == 0:
                return self._search_filesystem_by_project(project_number, doc_types)

            all_results = vs.find_similar_files(
                {"doc_type": " ".join(doc_types), "metadata": {"project_number": project_number}},
                n_results=20,
            )
            matched = [
                f for f in all_results
                if project_number.upper().replace("-", "").replace("_", "") in
                   f.get("project_number", "").upper().replace("-", "").replace("_", "")
            ]
            if not matched:
                matched = self._search_filesystem_by_project(project_number, doc_types)
            if doc_types:
                type_lower = [d.lower() for d in doc_types]
                matched = [
                    f for f in matched
                    if any(t in f.get("doc_type", "").lower() for t in type_lower)
                ] or matched
            return matched
        except Exception as e:
            self._log(f"Vector search failed: {e}, falling back to filesystem.")
            return self._search_filesystem_by_project(project_number, doc_types)

    def _search_filesystem_by_project(self, project_number: str, doc_types: list[str]) -> list[dict]:
        results = []
        search_term = project_number.upper().replace("-", "").replace("_", "")

        for search_root in [config.COMPANY_FILES_DIR, config.OUTPUTS_DIR]:
            if not search_root.exists():
                continue
            for fpath in search_root.rglob("*"):
                if not fpath.is_file():
                    continue
                fname_norm = fpath.name.upper().replace("-", "").replace("_", "")
                folder_norm = str(fpath.parent).upper().replace("-", "").replace("_", "")
                if search_term in fname_norm or search_term in folder_norm:
                    from core.file_classifier import FileClassifier
                    clf = FileClassifier()
                    doc_type = clf._detect_type(fpath.name, "")
                    results.append({
                        "filename": fpath.name,
                        "path": str(fpath),
                        "project_number": project_number,
                        "doc_type": doc_type,
                        "metadata": {},
                        "similarity": 1.0,
                    })

        if doc_types and results:
            type_lower = [d.lower() for d in doc_types]
            filtered = [
                f for f in results
                if any(t in f.get("doc_type", "").lower() for t in type_lower)
            ]
            return filtered if filtered else results

        return results

    def _semantic_search(self, query_text: str, n_results: int = 8) -> list[dict]:
        try:
            from core.vector_store import VectorStore
            vs = VectorStore()
            if vs.meta_count() == 0:
                return []
            dummy_result = {
                "doc_type": query_text,
                "metadata": {"vision_description": query_text},
            }
            return vs.find_similar_files(dummy_result, n_results=n_results)
        except Exception as e:
            self._log(f"Semantic search error: {e}")
            return []

    def _build_semantic_query(self, intent: dict) -> str:
        parts = []
        if intent.get("doc_types"):
            parts.extend(intent["doc_types"])
        if intent.get("process_context"):
            parts.append(intent["process_context"])
        if intent.get("unit_operations"):
            parts.extend(intent["unit_operations"])
        if intent.get("keywords"):
            parts.extend(intent["keywords"])
        return " ".join(parts)
