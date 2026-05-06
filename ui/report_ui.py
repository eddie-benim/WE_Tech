import streamlit as st
from pathlib import Path
import json

import config
from ui.components import (
    section_header, section_label, divider_label,
    api_key_guard, status_ok, status_warn, status_error,
    empty_state, progress_log, two_col
)


def _reference_count() -> int:
    return len([f for f in config.COMPANY_FILES_DIR.rglob("*") if f.is_file()])


def _run_report_agent(report_type: str, project_info: dict, use_web: bool) -> dict:
    from agents.report_agent import ReportAgent
    agent = ReportAgent(model=st.session_state.get("agent_model", config.AGENT_MODEL))
    return agent.run(
        report_type=report_type,
        project_info=project_info,
        use_web_search=use_web,
    )


def render_report_tab():
    section_header(
        "Report Generator",
        "Describe your project and the agent will draft a report using company references and web sources.",
    )

    ref_count = _reference_count()
    if ref_count == 0:
        status_warn("No reference documents found. Upload files in the Reference Library tab for best results.")
    else:
        status_ok(f"{ref_count} reference file(s) available.")

    st.markdown("#### Report Configuration")

    col_type, col_model = two_col((2, 1))
    with col_type:
        report_type = st.selectbox(
            "Report type",
            options=config.REPORT_TYPES,
        )
    with col_model:
        use_web = st.toggle("Web search", value=True, help="Allow the agent to search the web for standards and equations.")

    st.markdown("#### Project Details")

    col_name, col_num = two_col((3, 1))
    with col_name:
        project_name = st.text_input("Project name", placeholder="e.g. Offshore Gas Separation Facility")
    with col_num:
        project_number = st.text_input("Project number", placeholder="e.g. PRJ-042")

    client_name = st.text_input("Client / Company", placeholder="e.g. Acme Energy Ltd.")

    description = st.text_area(
        "Project description",
        placeholder=(
            "Describe the scope of work, key process streams, operating conditions, "
            "equipment involved, and any specific requirements or constraints."
        ),
        height=160,
    )

    col_extra, col_units = two_col((2, 1))
    with col_extra:
        special_notes = st.text_area(
            "Additional notes / constraints",
            placeholder="Standards to follow, client preferences, exclusions, etc.",
            height=80,
        )
    with col_units:
        unit_system = st.selectbox("Unit system", options=["SI (metric)", "Imperial (US)"])
        revision = st.text_input("Revision", value="Rev0")

    divider_label("Generate")

    ready = bool(project_name and description)
    if not ready:
        st.caption("Fill in project name and description to enable generation.")

    if st.button("Generate report →", disabled=not ready):
        if not api_key_guard():
            return

        project_info = {
            "project_name": project_name,
            "project_number": project_number,
            "client": client_name,
            "description": description,
            "special_notes": special_notes,
            "unit_system": unit_system,
            "revision": revision,
        }

        with st.spinner("Agent working…"):
            try:
                result = _run_report_agent(report_type, project_info, use_web)
                st.session_state["last_report"] = result
                st.session_state["last_report_type"] = report_type
                st.session_state["last_project_info"] = project_info
            except Exception as e:
                status_error(f"Agent error: {e}")
                return

    if "last_report" in st.session_state:
        result = st.session_state["last_report"]
        divider_label("Output")

        if result.get("log"):
            with st.expander("Agent log", expanded=False):
                progress_log(result["log"])

        tab_preview, tab_raw = st.tabs(["Preview", "Raw Markdown"])

        report_md = result.get("report", "")

        with tab_preview:
            st.markdown(report_md)

        with tab_raw:
            st.code(report_md, language="markdown")

        col_dl_md, col_dl_docx, _ = st.columns([1, 1, 3])

        with col_dl_md:
            st.download_button(
                "Download .md",
                data=report_md,
                file_name=f"{st.session_state['last_project_info']['project_name'].replace(' ', '_')}_{st.session_state['last_report_type'].replace(' ', '_')}.md",
                mime="text/markdown",
            )

        with col_dl_docx:
            if st.button("Export .docx"):
                try:
                    from tools.report_tools import markdown_to_docx
                    docx_bytes = markdown_to_docx(report_md)
                    st.download_button(
                        "Download .docx",
                        data=docx_bytes,
                        file_name=f"{project_name.replace(' ', '_')}.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    )
                except Exception as e:
                    status_warn(f"DOCX export unavailable: {e}")