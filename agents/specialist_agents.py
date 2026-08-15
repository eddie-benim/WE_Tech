# -*- coding: utf-8 -*-
from __future__ import annotations

import json as _json

import config
from agents.base_agent import BaseAgent
from core.metadata_extractor import MetadataExtractor
from prompts.specialist_prompts import (
    FLUID_TRACING_SYSTEM,
    PRESSURE_RATING_SYSTEM,
    ENGINEERING_DATA_SYSTEM,
    SIS_SAFETY_SYSTEM,
    CONTROL_VALVE_SYSTEM,
    UTILITY_BATTERY_SYSTEM,
    LINE_LIST_SYSTEM,
    COORDINATOR_SYSTEM, COORDINATOR_USER,
    PROJECT_ID_SYSTEM,
)

# (system prompt, output-budget hint) -- the budget hints are summed to size the single
# combined call's max_tokens rather than each specialist paying its own call overhead.
SPECIALIST_CONFIG = {
    "fluid_tracing":    (FLUID_TRACING_SYSTEM,    1500),
    "pressure_ratings": (PRESSURE_RATING_SYSTEM,  1000),
    "engineering_data": (ENGINEERING_DATA_SYSTEM, 1200),
    "sis_safety":       (SIS_SAFETY_SYSTEM,       1200),
    "control_valves":   (CONTROL_VALVE_SYSTEM,    1000),
    "utility_battery":  (UTILITY_BATTERY_SYSTEM,   900),
    "line_list":        (LINE_LIST_SYSTEM,        1000),
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

        from tools.file_tools import list_reference_files
        context = self._vision_tools.compact_vision_description(vision_text, (_CONTEXT,))
        ref_files = list_reference_files()

        results = {}
        deterministic_project_id = None
        include_project_id_in_call = bool(ref_files)
        if not ref_files:
            # No database to cross-reference against -- a second LLM call can't add
            # evidence beyond what the context pass already extracted, so resolve this
            # deterministically instead of paying for a call that can only restate it.
            deterministic_project_id = self._deterministic_project_id(context)

        if active or include_project_id_in_call:
            results = self._run_combined(
                active, vision_text, context, file_metadata or {}, ref_files, include_project_id_in_call
            )

        if deterministic_project_id:
            results["project_identification"] = deterministic_project_id
            self._log("Project identification resolved deterministically (no reference DB).")

        return {"specialist_results": results, "dispatch": dispatch, "log": self.log}

    def _run_combined(
        self,
        active: list[str],
        vision_text: str,
        context: str,
        file_metadata: dict,
        ref_files: list[dict],
        include_project_id: bool,
    ) -> dict:
        """One API call covering every active specialist section (plus project ID when a
        reference DB exists), instead of one call per section. Each section keeps its full
        original domain instructions verbatim -- concatenated, not summarised -- so nothing
        about analysis depth or precision changes. What's eliminated is paying for the
        vision-transcript input and per-call system-prompt overhead N times over."""
        if not active and not include_project_id:
            return {}

        evidence = self._vision_tools.compact_vision_description(vision_text)
        keys = list(active)

        system_parts = [
            "You are a team of process/piping engineering specialists analysing a single "
            "engineering drawing, working from a vision-extracted text description of that "
            "drawing (not the image itself) -- trust only what the description states, never "
            "invent details not present in it.\n\n"
            "Produce EVERY section listed below in a SINGLE JSON response. Each section has "
            "its own domain instructions and output format -- follow those instructions "
            "exactly when writing that section's text. If a section's content genuinely "
            "isn't present anywhere in the material provided, output an empty string for "
            "that key rather than fabricating content.\n"
        ]
        for key in keys:
            system, _budget = SPECIALIST_CONFIG[key]
            system_parts.append(f"\n=== SECTION: {key} ===\n{system}")

        user_parts = [f"=== VISION-EXTRACTED DESCRIPTION OF THE DRAWING ===\n{evidence}\n"]

        if include_project_id:
            keys.append("project_identification")
            system_parts.append(f"\n=== SECTION: project_identification ===\n{PROJECT_ID_SYSTEM}")
            meta_lines = [
                "Drawing title: " + str(file_metadata.get("description", "unknown")),
                "Client mentioned: " + str(file_metadata.get("client", "unknown")),
                "Revision: " + str(file_metadata.get("revision", "unknown")),
                "Current project_number field: " + str(file_metadata.get("project_number", "not set")),
            ]
            db_lines = ["- " + f["name"] + " (ext: " + f["extension"] + ")" for f in ref_files[:20]]
            user_parts.append(
                "\n=== METADATA CONTEXT (for project_identification) ===\n" + "\n".join(meta_lines)
            )
            user_parts.append(
                "\n\n=== OTHER FILES IN DATABASE (for project_identification cross-reference) ===\n"
                + "\n".join(db_lines)
            )

        system_parts.append(
            "\n\nFINAL OUTPUT -- valid JSON only, no markdown fences, no commentary outside "
            "the JSON object. One key per section above:\n{\n"
            + ",\n".join(f'  "{k}": "<text for {k}, or empty string>"' for k in keys)
            + "\n}\n"
        )
        user_parts.append(f"\n\nProduce JSON with exactly these keys: {', '.join(keys)}.")

        max_tokens = min(max(sum(SPECIALIST_CONFIG[k][1] for k in active) + (400 if include_project_id else 0), 1500), 7000)

        self._log(f"Running combined specialist call for: {', '.join(keys)} (1 API call instead of {len(keys)}).")
        result = self._chat_json(system="".join(system_parts), user="".join(user_parts), max_tokens=max_tokens, label="specialist_combined")

        if isinstance(result, dict) and result.get("parse_error"):
            self._log("Combined specialist call failed to parse -- returning empty results.")
            return {}

        out = {}
        for key in keys:
            value = result.get(key, "") if isinstance(result, dict) else ""
            if isinstance(value, (dict, list)):
                value = _json.dumps(value, indent=2)
            value = str(value).strip()
            if value and value.lower() not in ("n/a", "none", "not applicable"):
                out[key] = value
                self._log(f"  {key}: {len(value)} chars")
            else:
                self._log(f"  {key}: no content")
        return out

    @staticmethod
    def _label_value(text: str, label: str) -> str:
        import re
        m = re.search(rf"(?im)^\s*[-*]?\s*{re.escape(label)}\s*:\s*(.+?)\s*$", text)
        return m.group(1).strip() if m else ""

    def _deterministic_project_id(self, context: str) -> str:
        explicit_project = self._label_value(context, "PROJECT NUMBER")
        project_name = self._label_value(context, "PROJECT NAME")
        client = self._label_value(context, "CLIENT") or self._label_value(context, "CLIENT NAME")
        drawing = self._label_value(context, "DRAWING NUMBER")
        wo_po = self._label_value(context, "W.O.") or self._label_value(context, "P.O.")

        explicit_missing = not explicit_project or explicit_project.upper() in {
            "NOT STATED", "NOT DETERMINABLE", "N/A", "NONE"
        }
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
            label="coordinator_dispatch",
        )
        if result.get("parse_error"):
            self._log("Coordinator parse error -- defaulting to all passes.")
            return all_on | {"reasoning": "Default due to parse error."}
        return result
