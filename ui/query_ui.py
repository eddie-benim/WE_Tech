import streamlit as st
from pathlib import Path

import config
from ui.components import (
    section_header, section_label, divider_label,
    api_key_guard, status_ok, status_warn, empty_state,
    progress_log, two_col, tag_row
)

EXAMPLE_QUERIES = [
    "I am working on Project 0052 where I need to replace the steam-driven compressor with an electric motor. Show me relevant PFDs and P&IDs.",
    "Find all proposals we have done for gas compression projects.",
    "Show me any heat and energy balance reports similar to a two-stage compression system.",
    "What P&IDs do we have that include anti-surge control systems?",
    "Find documentation related to knock-out drums and suction systems across all projects.",
]


def _run_query(query: str) -> dict:
    from agents.query_agent import QueryAgent
    agent = QueryAgent(model=st.session_state.get("agent_model", config.AGENT_MODEL))
    return agent.run(query)


def _render_file_result(f: dict, rank: int):
    filename = f.get("filename", f.get("name", "unknown"))
    doc_type = f.get("doc_type", "Unknown")
    project_number = f.get("project_number", "—")
    similarity = f.get("similarity", None)
    meta = f.get("metadata", {})
    unit_ops = meta.get("unit_operations", [])
    path = f.get("path", f.get("organised_path", ""))

    with st.container(border=True):
        col_rank, col_info, col_sim = st.columns([0.5, 5, 1.5])

        with col_rank:
            st.markdown(
                f"<div style='font-family:IBM Plex Mono,monospace;font-size:1.1rem;"
                f"font-weight:700;color:#ccc;padding-top:0.2rem'>{rank}</div>",
                unsafe_allow_html=True,
            )

        with col_info:
            st.markdown(
                f"<span style='font-family:IBM Plex Mono,monospace;font-size:0.88rem;"
                f"font-weight:700'>{filename}</span>",
                unsafe_allow_html=True,
            )
            st.markdown(
                f"<span style='font-size:0.75rem;color:#888'>Project: {project_number}</span>",
                unsafe_allow_html=True,
            )
            tag_row([doc_type] + (unit_ops[:3] if isinstance(unit_ops, list) else []))

        with col_sim:
            if similarity is not None:
                pct = int(similarity * 100)
                color = "#2e7d32" if pct >= 80 else "#b45309" if pct >= 50 else "#aaa"
                st.markdown(
                    f"<div style='text-align:right;padding-top:0.3rem'>"
                    f"<span style='font-family:IBM Plex Mono,monospace;font-size:0.9rem;"
                    f"font-weight:700;color:{color}'>{pct}%</span><br>"
                    f"<span style='font-size:0.68rem;color:#aaa'>match</span></div>",
                    unsafe_allow_html=True,
                )

        if path and Path(path).exists():
            st.caption(f"📁 {path}")


def _render_intent_summary(intent: dict):
    with st.container(border=True):
        section_label("Parsed Intent")
        col1, col2 = two_col()
        with col1:
            st.markdown(
                f"<p style='font-size:0.82rem'><b>Project:</b> {intent.get('project_number') or 'not specified'}<br>"
                f"<b>Doc types:</b> {', '.join(intent.get('doc_types', [])) or 'any'}<br>"
                f"<b>Context:</b> {intent.get('process_context', '—')}</p>",
                unsafe_allow_html=True,
            )
        with col2:
            st.markdown(
                f"<p style='font-size:0.82rem'><b>Equipment:</b> {', '.join(intent.get('unit_operations', [])) or '—'}<br>"
                f"<b>Action:</b> {intent.get('action_context', '—')}<br>"
                f"<b>Similarity search:</b> {'yes' if intent.get('similarity_needed') else 'no'}</p>",
                unsafe_allow_html=True,
            )


def render_query_tab():
    section_header(
        "Document Search",
        "Ask in plain English. The assistant will find the most relevant files from your project database.",
    )

    ref_count = len([f for f in config.COMPANY_FILES_DIR.rglob("*") if f.is_file()])
    out_count = len([f for f in config.OUTPUTS_DIR.rglob("*") if f.is_file()]) if config.OUTPUTS_DIR.exists() else 0
    total = ref_count + out_count

    if total == 0:
        status_warn("No files in database yet. Upload and organise files first.")
    else:
        status_ok(f"{total} file(s) available across reference library and organised outputs.")

    st.markdown("#### What are you looking for?")

    with st.expander("Example queries", expanded=False):
        for eq in EXAMPLE_QUERIES:
            if st.button(eq, key=f"eq_{eq[:30]}"):
                st.session_state["query_input"] = eq
                st.rerun()

    query_input = st.text_area(
        "Your request",
        value=st.session_state.get("query_input", ""),
        placeholder=(
            "e.g. I am working on Project 0052 where I need to replace the steam-driven "
            "compressor with electric motors. Show me relevant PFDs and P&IDs."
        ),
        height=100,
        label_visibility="collapsed",
    )

    col_search, col_clear = st.columns([1, 5])
    with col_search:
        search_clicked = st.button("Search →", disabled=not query_input.strip())
    with col_clear:
        if st.button("Clear"):
            for key in ["query_input", "query_result"]:
                st.session_state.pop(key, None)
            st.rerun()

    if search_clicked and query_input.strip():
        if not api_key_guard():
            return
        with st.spinner("Searching…"):
            try:
                result = _run_query(query_input.strip())
                st.session_state["query_result"] = result
                st.session_state["query_input"] = query_input
            except Exception as e:
                st.error(f"Search error: {e}")
                return

    if "query_result" in st.session_state:
        result = st.session_state["query_result"]

        divider_label("Intent")
        _render_intent_summary(result.get("intent", {}))

        project_files = result.get("project_files", [])
        similar_files = result.get("similar_files", [])

        divider_label("Assistant Response")
        st.markdown(result.get("response", "No response generated."))

        if project_files:
            divider_label(f"Project Files ({len(project_files)})")
            for i, f in enumerate(project_files, 1):
                _render_file_result(f, i)

        if similar_files:
            divider_label(f"Similar Files Across Projects ({len(similar_files)})")
            for i, f in enumerate(similar_files, 1):
                _render_file_result(f, i)

        if not project_files and not similar_files:
            empty_state("🔍", "No matching files found. Try uploading and indexing more reference documents.")

        with st.expander("Agent log", expanded=False):
            progress_log(result.get("log", []))
