from __future__ import annotations

import config
from agents.base_agent import BaseAgent
from prompts.specialist_prompts import (
    FLUID_TRACING_SYSTEM, FLUID_TRACING_USER,
    PRESSURE_RATING_SYSTEM, PRESSURE_RATING_USER,
    ENGINEERING_DATA_SYSTEM, ENGINEERING_DATA_USER,
    SIS_SAFETY_SYSTEM, SIS_SAFETY_USER,
    CONTROL_VALVE_SYSTEM, CONTROL_VALVE_USER,
    UTILITY_BATTERY_SYSTEM, UTILITY_BATTERY_USER,
    LINE_LIST_SYSTEM, LINE_LIST_USER,
    COORDINATOR_SYSTEM, COORDINATOR_USER,
    PROJECT_ID_SYSTEM, PROJECT_ID_USER,
)

SPECIALIST_CONFIG = {
    "fluid_tracing":    (FLUID_TRACING_SYSTEM,    FLUID_TRACING_USER,    1500),
    "pressure_ratings": (PRESSURE_RATING_SYSTEM,  PRESSURE_RATING_USER,  1000),
    "engineering_data": (ENGINEERING_DATA_SYSTEM,  ENGINEERING_DATA_USER, 1200),
    "sis_safety":       (SIS_SAFETY_SYSTEM,        SIS_SAFETY_USER,       1200),
    "control_valves":   (CONTROL_VALVE_SYSTEM,     CONTROL_VALVE_USER,    1000),
    "utility_battery":  (UTILITY_BATTERY_SYSTEM,   UTILITY_BATTERY_USER,   900),
    "line_list":        (LINE_LIST_SYSTEM,          LINE_LIST_USER,        1000),
}

DISPATCH_KEY_MAP = {
    "run_fluid_tracing":   "fluid_tracing",
    "run_pressure_rating": "pressure_ratings",
    "run_engineering_data":"engineering_data",
    "run_sis_safety":      "sis_safety",
    "run_control_valve":   "control_valves",
    "run_utility_battery": "utility_battery",
    "run_line_list":       "line_list",
}


class SpecialistCoordinator(BaseAgent):

    def run(self, doc_type: str, vision_text: str, file_metadata: dict | None = None) -> dict:
        self.log = []

        if not vision_text or len(vision_text.strip()) < 100:
            self._log("Vision text too short — skipping specialist analysis.")
            return {"specialist_results": {}, "log": self.log}

        self._log("Determining specialist passes needed…")
        dispatch = self._decide_dispatch(doc_type, vision_text)
        self._log(f"Dispatch: {dispatch.get('reasoning', '—')}")

        active = [
            result_key
            for dispatch_key, result_key in DISPATCH_KEY_MAP.items()
            if dispatch.get(dispatch_key)
        ]
        self._log(f"Passes to run: {', '.join(active) if active else 'none'}")

        results = {}
        for result_key in active:
            system, user_template, max_tok = SPECIALIST_CONFIG[result_key]
            self._log(f"Running {result_key}…")
            try:
                output = self._chat(
                    system=system,
                    user=user_template.format(vision_text=vision_text),
                    max_tokens=max_tok,
                )
                if output.strip():
                    results[result_key] = output
                    self._log(f"  {result_key} complete ({len(output)} chars).")
                else:
                    self._log(f"  {result_key} returned empty — skipping.")
            except Exception as e:
                self._log(f"  {result_key} failed: {e}")

        self._log("Running project identification…")
        try:
            project_id = self._run_project_id(vision_text, file_metadata or {})
            if project_id.strip():
                results["project_identification"] = project_id
                self._log("Project identification complete.")
        except Exception as e:
            self._log(f"Project identification failed: {e}")

        return {"specialist_results": results, "dispatch": dispatch, "log": self.log}

    def _run_project_id(self, vision_text: str, file_metadata: dict) -> str:
        import config
        from tools.file_tools import list_reference_files

        meta_summary = (
            f"Drawing title: {file_metadata.get('description', 'unknown')}
"
            f"Client mentioned: {file_metadata.get('client', 'unknown')}
"
            f"Revision: {file_metadata.get('revision', 'unknown')}
"
            f"Current project_number field: {file_metadata.get('project_number', 'not set')}
"
            f"Vision context excerpt: {vision_text[:600]}"
        )

        ref_files = list_reference_files()
        if ref_files:
            db_summary = "
".join(
                f"- {f['name']} (ext: {f['extension']})"
                for f in ref_files[:20]
            )
        else:
            db_summary = "No other files currently in the database."

        return self._chat(
            system=PROJECT_ID_SYSTEM,
            user=PROJECT_ID_USER.format(
                metadata_summary=meta_summary,
                db_files_summary=db_summary,
            ),
            max_tokens=400,
        )

    def _decide_dispatch(self, doc_type: str, vision_text: str) -> dict:
        excerpt = vision_text[:1000]
        result = self._chat_json(
            system=COORDINATOR_SYSTEM,
            user=COORDINATOR_USER.format(doc_type=doc_type, vision_excerpt=excerpt),
            max_tokens=250,
        )
        if result.get("parse_error"):
            self._log("Coordinator parse error — defaulting to all passes.")
            return {k: True for k in DISPATCH_KEY_MAP} | {"reasoning": "Default due to parse error."}
        return result
