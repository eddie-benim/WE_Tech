from __future__ import annotations

import config
from agents.base_agent import BaseAgent
from tools.report_tools import build_report_context, render_skeleton, trim_to_token_budget
from tools.web_tools import web_search, fetch_page_text, format_search_results
from prompts.report_prompts import (
    REPORT_SYSTEM_PROMPT,
    build_report_user_prompt,
    build_web_search_query,
)


class ReportAgent(BaseAgent):

    def run(self, report_type: str, project_info: dict, use_web_search: bool = True) -> dict:
        self.log = []

        self._log(f"Starting report generation: {report_type}")
        self._log(f"Project: {project_info.get('project_name', '—')}")

        self._log("Rendering report skeleton…")
        skeleton = render_skeleton(report_type, project_info)

        self._log("Retrieving company reference context…")
        reference_context = build_report_context(report_type, project_info, top_k=config.TOP_K_RETRIEVAL)
        reference_context = trim_to_token_budget(reference_context, config.REFERENCE_TOKEN_BUDGET)

        if reference_context.startswith("No reference"):
            self._log("No company references found — proceeding without.")
        else:
            self._log(f"Retrieved reference context ({self._token_count(reference_context)} tokens).")

        web_results = ""
        if use_web_search:
            self._log("Searching web for relevant standards and equations…")
            query = build_web_search_query(report_type, project_info)
            search_hits = web_search(query, max_results=5)
            web_results = format_search_results(search_hits)

            if search_hits and not search_hits[0].get("error"):
                top_url = search_hits[0].get("url", "")
                if top_url:
                    self._log(f"Fetching top result: {top_url}")
                    page_text = fetch_page_text(top_url, max_chars=3000)
                    web_results += f"\n\n--- Full page: {top_url} ---\n{page_text}"

            web_results = trim_to_token_budget(web_results, 3000)
            self._log(f"Web research complete ({self._token_count(web_results)} tokens).")

        self._log("Calling language model to draft report…")
        user_prompt = build_report_user_prompt(
            report_type=report_type,
            project_info=project_info,
            skeleton=skeleton,
            reference_context=reference_context,
            web_results=web_results,
        )

        report_md = self._chat(
            system=REPORT_SYSTEM_PROMPT,
            user=user_prompt,
            max_tokens=config.MAX_COMPLETION_TOKENS,
        )

        self._log("Report draft complete.")

        return {
            "report": report_md,
            "report_type": report_type,
            "project_info": project_info,
            "log": self.log,
        }