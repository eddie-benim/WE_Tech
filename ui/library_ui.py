import streamlit as st
import shutil
from pathlib import Path

import config
from ui.components import (
    section_header, section_label, file_card,
    status_ok, status_warn, empty_state, divider_label, tag_row
)


def _save_uploaded_file(uploaded_file, dest_dir: Path) -> Path:
    dest = dest_dir / uploaded_file.name
    dest.write_bytes(uploaded_file.getbuffer())
    return dest


def _get_indexed_files() -> list[Path]:
    return sorted(
        [f for f in config.COMPANY_FILES_DIR.rglob("*") if f.is_file()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )


def _ext_to_fmt(ext: str) -> str:
    return config.SUPPORTED_EXTENSIONS.get(ext.lower(), ext.upper().lstrip("."))


def _guess_file_type(filename: str) -> str:
    lower = filename.lower()
    for doc_type, keywords in config.FILE_TYPE_KEYWORDS.items():
        for kw in keywords:
            if kw in lower:
                return doc_type
    return "Unknown"


def render_library_tab():
    section_header(
        "Reference Library",
        "Upload company reference documents here. These are used by the Report Generator and File Organiser as context.",
    )

    st.markdown("#### Upload Reference Documents")

    uploaded = st.file_uploader(
        "Drop files here",
        accept_multiple_files=True,
        type=list(config.SUPPORTED_EXTENSIONS.keys()),
        label_visibility="collapsed",
    )

    if uploaded:
        saved = []
        for f in uploaded:
            path = _save_uploaded_file(f, config.COMPANY_FILES_DIR)
            saved.append(path)

        status_ok(f"{len(saved)} file(s) saved to reference library.")

        if st.button("Index uploaded files →"):
            with st.spinner("Indexing…"):
                try:
                    from core.vector_store import VectorStore
                    vs = VectorStore()
                    results = vs.index_directory(config.COMPANY_FILES_DIR)
                    status_ok(f"Indexed {results['indexed']} chunk(s) from {results['files']} file(s).")
                except Exception as e:
                    status_warn(f"Indexing skipped: {e}")

    divider_label("Indexed Files")

    indexed = _get_indexed_files()

    if not indexed:
        empty_state("📭", "No reference files uploaded yet.")
        return

    section_label(f"{len(indexed)} file(s) in library")

    col_search, col_filter = st.columns([3, 1])
    with col_search:
        search_term = st.text_input("Search", placeholder="Filter by name…", label_visibility="collapsed")
    with col_filter:
        type_filter = st.selectbox(
            "Type",
            options=["All"] + list(config.FILE_TYPE_KEYWORDS.keys()),
            label_visibility="collapsed",
        )

    filtered = indexed
    if search_term:
        filtered = [f for f in filtered if search_term.lower() in f.name.lower()]
    if type_filter != "All":
        filtered = [f for f in filtered if _guess_file_type(f.name) == type_filter]

    if not filtered:
        empty_state("🔍", "No files match that filter.")
        return

    for fpath in filtered:
        ext = fpath.suffix
        fmt = _ext_to_fmt(ext)
        doc_type = _guess_file_type(fpath.name)
        size_kb = fpath.stat().st_size / 1024
        file_card(
            name=fpath.name,
            file_type=doc_type,
            fmt=fmt,
            size_kb=size_kb,
        )

    divider_label("Danger Zone")

    with st.expander("Clear reference library", expanded=False):
        st.warning("This will permanently delete all uploaded reference files.")
        if st.button("Delete all reference files", type="primary"):
            shutil.rmtree(config.COMPANY_FILES_DIR)
            config.COMPANY_FILES_DIR.mkdir(parents=True, exist_ok=True)
            st.rerun()