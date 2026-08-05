import streamlit as st
import shutil
import json
from pathlib import Path

import config
from ui.components import (
    section_header, section_label, divider_label,
    api_key_guard, status_ok, status_warn, status_error,
    empty_state, progress_log, two_col, tag_row
)

STAGING_DIR = config.DATA_DIR / "staging"
STAGING_DIR.mkdir(parents=True, exist_ok=True)


def _save_to_staging(uploaded_file) -> Path:
    dest = STAGING_DIR / uploaded_file.name
    dest.write_bytes(uploaded_file.getbuffer())
    return dest


def _run_file_agent(paths: list[Path]) -> tuple[list[dict], list[str]]:
    from agents.file_agent import FileAgent
    agent = FileAgent(model=st.session_state.get("agent_model", config.AGENT_MODEL))
    results = agent.analyze_files(paths)
    return results, agent.log


def _apply_organisation(results: list[dict], output_root: Path):
    from core.organizer import Organizer
    org = Organizer(output_root=output_root)
    return org.organize(results)


def _render_file_card(r: dict):
    original_name = r.get("original_name", "unknown")
    suggested_name = r.get("suggested_name", original_name)
    doc_type = r.get("doc_type", "Unknown")
    fmt = r.get("format", "")
    size_kb = r.get("size_kb", 0)
    confidence = r.get("confidence", "")
    meta = r.get("metadata", {})
    unit_ops = meta.get("unit_operations", [])
    instruments = meta.get("instrumentation", [])
    control_loops = meta.get("control_loops", [])
    unique_elements = meta.get("unique_elements", [])
    vision_desc = meta.get("vision_description", "")
    project_match = r.get("project_match", {})
    similar_files = r.get("similar_files", [])

    confidence_color = {"high": "#2e7d32", "medium": "#b45309", "low": "#c62828"}.get(confidence, "#aaa")

    with st.container(border=True):
        col_name, col_conf = st.columns([4, 1])
        with col_name:
            st.markdown(
                f"<span style='font-family:IBM Plex Mono,monospace;font-size:0.9rem;font-weight:700'>{suggested_name}</span>",
                unsafe_allow_html=True,
            )
            st.markdown(
                f"<span style='font-size:0.75rem;color:#aaa'>Original: {original_name}</span>",
                unsafe_allow_html=True,
            )
        with col_conf:
            st.markdown(
                f"<div style='text-align:right'>"
                f"<span style='font-family:IBM Plex Mono,monospace;font-size:0.7rem;color:{confidence_color}'>"
                f"● {confidence.upper() if confidence else 'UNKNOWN'}</span><br>"
                f"<span style='font-size:0.72rem;color:#aaa'>{size_kb:.1f} KB</span>"
                f"</div>",
                unsafe_allow_html=True,
            )

        tag_row([doc_type, fmt])

        if unit_ops:
            st.markdown(
                "<div style='margin-top:0.6rem'><span style='font-family:IBM Plex Mono,monospace;"
                "font-size:0.68rem;color:#aaa;letter-spacing:0.08em;text-transform:uppercase'>"
                "Unit Operations</span></div>",
                unsafe_allow_html=True,
            )
            tag_row(unit_ops if isinstance(unit_ops, list) else [unit_ops])

        if instruments:
            st.markdown(
                "<div style='margin-top:0.4rem'><span style='font-family:IBM Plex Mono,monospace;"
                "font-size:0.68rem;color:#aaa;letter-spacing:0.08em;text-transform:uppercase'>"
                "Instrumentation</span></div>",
                unsafe_allow_html=True,
            )
            tag_row(instruments if isinstance(instruments, list) else [instruments])

        if control_loops:
            st.markdown(
                "<div style='margin-top:0.4rem'><span style='font-family:IBM Plex Mono,monospace;"
                "font-size:0.68rem;color:#aaa;letter-spacing:0.08em;text-transform:uppercase'>"
                "Control Loops</span></div>",
                unsafe_allow_html=True,
            )
            tag_row(control_loops if isinstance(control_loops, list) else [control_loops])

        if unique_elements:
            st.markdown(
                "<div style='margin-top:0.4rem'><span style='font-family:IBM Plex Mono,monospace;"
                "font-size:0.68rem;color:#aaa;letter-spacing:0.08em;text-transform:uppercase'>"
                "Unique Elements</span></div>",
                unsafe_allow_html=True,
            )
            tag_row(unique_elements if isinstance(unique_elements, list) else [unique_elements])

        if project_match and project_match.get("matched_project_number"):
            pnum = project_match.get("matched_project_number", "")
            pconf = project_match.get("matched_project_confidence", "")
            reasoning = project_match.get("reasoning", "")
            pcolor = {"high": "#2e7d32", "medium": "#b45309", "low": "#c62828"}.get(pconf, "#aaa")
            st.markdown(
                f"<div style='margin-top:0.6rem;padding:0.4rem 0.6rem;background:#f5f5f0;border-left:3px solid {pcolor}'>"
                f"<span style='font-family:IBM Plex Mono,monospace;font-size:0.75rem;font-weight:600'>Project match: {pnum}</span>"
                f"<span style='font-size:0.72rem;color:#888;margin-left:0.6rem'>({pconf} confidence)</span><br>"
                f"<span style='font-size:0.75rem;color:#555'>{reasoning}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )

        specialist = meta.get("specialist_analysis", {})

        SPECIALIST_SECTIONS = [
            ("fluid_tracing",    "🔵 Process fluid tracing"),
            ("pressure_ratings", "🔴 Pressure & design conditions"),
            ("sis_safety",       "⚠️ Safety systems (SIS / ESD / alarms)"),
            ("control_valves",   "🎛️ Control valves & loops"),
            ("line_list",        "📋 Line list"),
            ("engineering_data", "🔧 Engineering data (piping, valves, stamps)"),
            ("utility_battery",  "🔌 Utility connections & battery limits"),
        ]

        for key, label in SPECIALIST_SECTIONS:
            if specialist.get(key):
                with st.expander(label, expanded=False):
                    st.markdown(
                        f"<pre style='font-size:0.78rem;color:#333;white-space:pre-wrap;"
                        f"background:#f9f9f7;padding:0.6rem;border-radius:3px'>"
                        f"{specialist[key]}</pre>",
                        unsafe_allow_html=True,
                    )

        with st.expander("🔍 Vision analysis (raw)", expanded=False):
            if vision_desc:
                st.markdown(
                    f"<p style='font-size:0.78rem;color:#666;white-space:pre-wrap'>{vision_desc}</p>",
                    unsafe_allow_html=True,
                )
            else:
                st.caption("No vision analysis available for this file.")

        if similar_files:
            with st.expander(f"Similar files in database ({len(similar_files)})", expanded=False):
                for sf in similar_files:
                    sim_pct = int(sf.get("similarity", 0) * 100)
                    st.markdown(
                        f"<span style='font-family:IBM Plex Mono,monospace;font-size:0.78rem'>"
                        f"{sf.get('filename', '')} — {sf.get('doc_type', '')} — "
                        f"Project: {sf.get('project_number', '—')} — "
                        f"<b>{sim_pct}% similar</b></span>",
                        unsafe_allow_html=True,
                    )

        meta_display = {k: v for k, v in meta.items() if k != "vision_description"}
        if meta_display:
            with st.expander("All metadata", expanded=False):
                st.json(meta_display)


def render_file_tab():
    section_header(
        "File Organiser",
        "Drop engineering documents here to auto-classify, tag with metadata, rename, and sort into project folders.",
    )

    uploaded = st.file_uploader(
        "Drop files to organise",
        accept_multiple_files=True,
        type=list(config.SUPPORTED_EXTENSIONS.keys()),
        label_visibility="collapsed",
        key="file_organiser_uploader",
    )

    if uploaded:
        staged_paths = []
        for f in uploaded:
            p = _save_to_staging(f)
            staged_paths.append(p)
        st.session_state["staged_paths"] = staged_paths
        status_ok(f"{len(staged_paths)} file(s) staged.")

    staged = st.session_state.get("staged_paths", [])
    staged = [p for p in staged if Path(p).exists()]

    if not staged:
        empty_state("📂", "No files staged yet. Drop files above to begin.")
        return

    divider_label("Staged Files")
    section_label(f"{len(staged)} file(s) ready for analysis")

    for p in staged:
        p = Path(p)
        ext = p.suffix
        fmt = config.SUPPORTED_EXTENSIONS.get(ext.lower(), ext.upper().lstrip("."))
        size_kb = p.stat().st_size / 1024
        st.markdown(
            f"<span style='font-family:IBM Plex Mono,monospace;font-size:0.82rem'>📄 {p.name}</span> "
            f"<span style='font-size:0.75rem;color:#aaa'>({fmt} · {size_kb:.1f} KB)</span>",
            unsafe_allow_html=True,
        )

    divider_label("Analysis")

    col_ai, col_out = two_col((2, 1))
    with col_ai:
        use_ai = st.toggle(
            "Use AI for ambiguous files",
            value=True,
            help="Falls back to rule-based classification when AI is off.",
        )
    with col_out:
        output_label = st.text_input(
            "Output folder name",
            value="organised",
            label_visibility="visible",
        )

    if st.button("Analyse & classify →"):
        if use_ai and not api_key_guard():
            return

        with st.spinner("Classifying files… vision analysis may take 10–20 seconds per image."):
            try:
                if use_ai:
                    results, agent_log = _run_file_agent([Path(p) for p in staged])
                    st.session_state["agent_log"] = agent_log
                else:
                    from core.file_classifier import FileClassifier
                    clf = FileClassifier()
                    results = [clf.classify(Path(p)) for p in staged]
                    st.session_state["agent_log"] = []
                st.session_state["classification_results"] = results
            except Exception as e:
                status_error(f"Classification error: {e}")
                return

    if "agent_log" in st.session_state and st.session_state["agent_log"]:
        with st.expander("Agent log", expanded=False):
            progress_log(st.session_state["agent_log"])

    if "classification_results" in st.session_state:
        results: list[dict] = st.session_state["classification_results"]

        divider_label("Classification Results")

        for r in results:
            _render_file_card(r)

        divider_label("Organise")

        st.markdown(
            "<p style='font-size:0.85rem;color:#666'>Review the classifications above, "
            "then click to copy files into organised folders under "
            "<code>data/outputs/{output_folder}</code>.</p>",
            unsafe_allow_html=True,
        )

        if st.button("Apply organisation →"):
            output_root = config.OUTPUTS_DIR / output_label
            with st.spinner("Organising files…"):
                try:
                    summary = _apply_organisation(results, output_root)
                    st.session_state["org_summary"] = summary
                    st.session_state["org_output_root"] = str(output_root)
                except Exception as e:
                    status_error(f"Organisation error: {e}")
                    return

    if "org_summary" in st.session_state:
        summary = st.session_state["org_summary"]
        output_root = st.session_state.get("org_output_root", "")

        divider_label("Organisation Summary")
        status_ok(f"{summary.get('moved', 0)} file(s) organised into {summary.get('folders_created', 0)} folder(s).")
        st.caption(f"Output: {output_root}")

        if summary.get("tree"):
            with st.expander("Folder tree", expanded=True):
                st.code(summary["tree"], language="")

        col_clear, _ = two_col((1, 3))
        with col_clear:
            if st.button("Clear staging area"):
                shutil.rmtree(STAGING_DIR)
                STAGING_DIR.mkdir(parents=True, exist_ok=True)
                for key in ["staged_paths", "classification_results", "org_summary", "org_output_root", "agent_log"]:
                    st.session_state.pop(key, None)
                st.rerun()
