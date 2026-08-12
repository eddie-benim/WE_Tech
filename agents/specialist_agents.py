# -*- coding: utf-8 -*-
from __future__ import annotations

import config
from agents.base_agent import BaseAgent
from core.metadata_extractor import MetadataExtractor
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
    "run_engineering_data": "engineering_data",
    "run_sis_safety":      "sis_safety",
    "run_control_valve":   "control_valves",
    "run_utility_battery": "utility_battery",
    "run_line_list":       "line_list",
}

_CONTEXT = "CONTEXT ANALYSIS"
_INSTRUMENTS = "INSTRUMENT TAGS (multi-tile extraction)"
_PIPE_SPECS = "PIPE SPECIFICATIONS (reconciled across tiles)"
_VALVES = "VALVE AND FITTING SURVEY (reconciled across tiles)"

# Each specialist receives only the evidence it can actually use. This preserves the
# specialist separation while avoiding seven re-sends of the entire vision transcript.
SPECIALIST_SECTIONS = {
    "fluid_tracing":    (_CONTEXT, _INSTRUMENTS, _PIPE_SPECS, _VALVES),
    "pressure_ratings": (_CONTEXT, _INSTRUMENTS, _PIPE_SPECS, _VALVES),
    "engineering_data": (_CONTEXT, _INSTRUMENTS, _PIPE_SPECS, _VALVES),
    "sis_safety":       (_CONTEXT, _INSTRUMENTS, _VALVES),
    "control_valves":   (_CONTEXT, _INSTRUMENTS, _VALVES),
    "utility_battery":  (_CONTEXT, _PIPE_SPECS, _VALVES),
    "line_list":        (_CONTEXT, _PIPE_SPECS, _VALVES),
}


class SpecialistCoordinator(BaseAgent):

    def __init__(self, model: str | None = None):
        super().__init__(model)
        self._vision_tools = MetadataExtractor()

    def run(self, doc_type: str, vision_text: str, file_metadata: dict | None = None) -> dict:
        self.log = []

        if not vision_text or len(vision_text.strip()) < 100:
            self._log("Vision text too short -- skipping specialist analysis.")
            return {"specialist_results": {}, "log": self.log}

        self._log("Determining specialist passes needed...")
        dispatch = self._decide_dispatch(doc_type, vision_text)
        self._log(f"Dispatch: {dispatch.get('reasoning', '--')}")

        active = [
            result_key
            for dispatch_key, result_key in DISPATCH_KEY_MAP.items()
            if dispatch.get(dispatch_key)
        ]
        self._log(f"Passes to run: {', '.join(active) if active else 'none'}")

        results = {}
        for result_key in active:
            system, user_template, max_tok = SPECIALIST_CONFIG[result_key]
            self._log(f"Running {result_key}...")
            try:
                evidence = self._specialist_context(result_key, vision_text)
                output = self._chat(
                    system=system,
                    user=user_template.format(vision_text=evidence),
                    max_tokens=max_tok,
                )
                if output.strip():
                    results[result_key] = output
                    self._log(f"  {result_key} complete ({len(output)} chars).")
                else:
                    self._log(f"  {result_key} returned empty -- skipping.")
            except Exception as e:
                self._log(f"  {result_key} failed: {e}")

        self._log("Running project identification...")
        try:
            project_id = self._run_project_id(vision_text, file_metadata or {})
            if project_id.strip():
                results["project_identification"] = project_id
                self._log("Project identification complete.")
        except Exception as e:
            self._log(f"Project identification failed: {e}")

        return {"specialist_results": results, "dispatch": dispatch, "log": self.log}

    def _specialist_context(self, result_key: str, vision_text: str) -> str:
        sections = SPECIALIST_SECTIONS.get(result_key)
        if not sections:
            return self._vision_tools.compact_vision_description(vision_text)
        return self._vision_tools.compact_vision_description(vision_text, sections)

    @staticmethod
    def _label_value(text: str, label: str) -> str:
        import re
        m = re.search(rf"(?im)^\s*[-*]?\s*{re.escape(label)}\s*:\s*(.+?)\s*$", text)
        return m.group(1).strip() if m else ""

    def _run_project_id(self, vision_text: str, file_metadata: dict) -> str:
        from tools.file_tools import list_reference_files

        context = self._vision_tools.compact_vision_description(vision_text, (_CONTEXT,))
        explicit_project = self._label_value(context, "PROJECT NUMBER")
        project_name = self._label_value(context, "PROJECT NAME")
        client = self._label_value(context, "CLIENT") or self._label_value(context, "CLIENT NAME")
        drawing = self._label_value(context, "DRAWING NUMBER")
        wo_po = self._label_value(context, "W.O.") or self._label_value(context, "P.O.")

        ref_files = list_reference_files()
        explicit_missing = not explicit_project or explicit_project.upper() in {
            "NOT STATED", "NOT DETERMINABLE", "N/A", "NONE"
        }

        # The context pass was explicitly instructed to distinguish drawing/PO numbers from
        # project numbers. With no database files to cross-reference, another LLM call cannot
        # add evidence. Return the same archivist conclusion deterministically.
        if not ref_files:
            if explicit_missing:
                project_value = "NOT DETERMINABLE FROM THIS DOCUMENT ALONE"
                confidence = "none"
                reasoning = "No explicit project number is stated and no database files are available for cross-reference."
            else:
                project_value = explicit_project
                confidence = "high"
                reasoning = "Project number is explicitly labelled in the drawing context."
            return (
                f"PROJECT NUMBER: {project_value}\n"
                f"PROJECT NAME: {project_name or 'N/A'}\n"
                f"CLIENT: {client or 'N/A'}\n"
                f"DRAWING NUMBER: {drawing or 'N/A'}\n"
                f"W.O. / P.O.: {wo_po or 'N/A'}\n"
                "INFERRED PROJECT MATCH: N/A\n"
                f"CONFIDENCE: {confidence}\n"
                f"REASONING: {reasoning}"
            )

        meta_lines = [
            "Drawing title: " + str(file_metadata.get("description", "unknown")),
            "Client mentioned: " + str(file_metadata.get("client", "unknown")),
            "Revision: " + str(file_metadata.get("revision", "unknown")),
            "Current project_number field: " + str(file_metadata.get("project_number", "not set")),
            "Vision context: " + context[:1200],
        ]
        meta_summary = "\n".join(meta_lines)

        db_lines = ["- " + f["name"] + " (ext: " + f["extension"] + ")" for f in ref_files[:20]]
        db_summary = "\n".join(db_lines)

        return self._chat(
            system=PROJECT_ID_SYSTEM,
            user=PROJECT_ID_USER.format(
                metadata_summary=meta_summary,
                db_files_summary=db_summary,
            ),
            max_tokens=400,
        )

    def _decide_dispatch(self, doc_type: str, vision_text: str) -> dict:
        dt = (doc_type or "Unknown").strip()
        if dt == "Unknown":
            context = self._vision_tools.compact_vision_description(vision_text, (_CONTEXT,))
            context_dt = self._vision_tools._doc_type_from_context(context)
            if context_dt:
                dt = context_dt
        all_on = {k: True for k in DISPATCH_KEY_MAP}
        all_off = {k: False for k in DISPATCH_KEY_MAP}

        # These are the exact dispatch rules that used to be sent to an LLM. For known
        # document types there is nothing probabilistic to decide, so do it locally.
        if dt in {"P&ID", "System Diagram"}:
            return all_on | {"reasoning": f"Deterministic {dt} dispatch: all specialist passes."}
        if dt == "PFD":
            out = all_off.copy()
            for key in ("run_fluid_tracing", "run_pressure_rating", "run_engineering_data",
                        "run_utility_battery", "run_line_list"):
                out[key] = True
            return out | {"reasoning": "Deterministic PFD dispatch."}
        if dt in {"Data Sheet", "Equipment Spec", "Equipment Sizing"}:
            out = all_off.copy()
            out["run_pressure_rating"] = True
            out["run_engineering_data"] = True
            return out | {"reasoning": f"Deterministic {dt} dispatch."}
        if dt == "Isometric":
            out = all_off.copy()
            out["run_engineering_data"] = True
            out["run_line_list"] = True
            return out | {"reasoning": "Deterministic Isometric dispatch."}
        if dt == "GA Drawing":
            out = all_off.copy()
            out["run_engineering_data"] = True
            return out | {"reasoning": "Deterministic GA dispatch."}
        if dt in {"Proposal", "Report", "Tech Memo", "General Letter"}:
            return all_off | {"reasoning": f"Deterministic {dt} dispatch: no specialist passes."}
        if dt in {"Cause & Effect", "Cause and Effect Matrix", "Hazop", "HAZOP"}:
            out = all_off.copy()
            out["run_sis_safety"] = True
            return out | {"reasoning": f"Deterministic {dt} dispatch."}

        # Unknown remains evidence-dependent, so retain the coordinator model only here.
        excerpt = self._vision_tools.compact_vision_description(vision_text, (_CONTEXT,))[:1000]
        result = self._chat_json(
            system=COORDINATOR_SYSTEM,
            user=COORDINATOR_USER.format(doc_type=dt, vision_excerpt=excerpt),
            max_tokens=250,
        )
        if result.get("parse_error"):
            self._log("Coordinator parse error -- defaulting to all passes.")
            return all_on | {"reasoning": "Default due to parse error."}
        return result
