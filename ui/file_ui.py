import streamlit as st
import shutil
import json
from pathlib import Path

import config
from ui.components import (
    section_header, section_label, divider_label,
    api_key_guard, status_ok, status_warn, status_error,
    empty_state, file_card, progress_log, two_col, tag_row
)


STAGING_DIR = config.DATA_DIR / "staging"
STAGING_DIR.mkdir(parents=True, exist_ok=True)


def _save_to_staging(uploaded_file) -> Path:
    dest = STAGING_DIR / uploaded_file.name
    dest.write_bytes(uploaded_file.getbuffer())
    return dest


def _run_file_agent(paths: list[Path]) -> list[dict]:
    from agents.file_agent import FileAgent
    agent = FileAgent(model=st.session_state.get("agent_model", config.AGENT_MODEL))
    return agent.analyze_files(paths)


def _apply_organisation(results: list[dict], output_root: Path):
    from core.organizer import Organizer
    org = Organizer(output_root=output_root)
    return org.organize(results)


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

        with st.spinner("Classifying files…"):
            try:
                if use_ai:
                    results = _run_file_agent([Path(p) for p in staged])
                else:
                    from core.file_classifier import FileClassifier
                    clf = FileClassifier()
                    results = [clf.classify(Path(p)) for p in staged]
                st.session_state["classification_results"] = results
            except Exception as e:
                status_error(f"Classification error: {e}")
                return

    if "classification_results" in st.session_state:
        results: list[dict] = st.session_state["classification_results"]

        divider_label("Classification Results")

        for r in results:
            file_card(
                name=r.get("suggested_name", r.get("original_name", "unknown")),
                file_type=r.get("doc_type", "Unknown"),
                fmt=r.get("format", ""),
                size_kb=r.get("size_kb", 0),
                metadata=r.get("metadata", {}),
            )

        divider_label("Organise")

        st.markdown(
            "<p style='font-size:0.85rem;color:#666'>Review the classifications above, then click to copy files into organised folders under <code>data/outputs/{output_folder}</code>.</p>",
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
                for key in ["staged_paths", "classification_results", "org_summary", "org_output_root"]:
                    st.session_state.pop(key, None)
                st.rerun()