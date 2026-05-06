import streamlit as st
from pathlib import Path


def section_header(title: str, subtitle: str = ""):
    st.markdown(f"### {title}")
    if subtitle:
        st.markdown(
            f"<p style='font-size:0.85rem;color:#777;margin-top:-0.6rem'>{subtitle}</p>",
            unsafe_allow_html=True,
        )


def tag_pill(label: str):
    st.markdown(
        f"<span class='tag-pill'>{label}</span>",
        unsafe_allow_html=True,
    )


def tag_row(labels: list[str]):
    pills = "".join(
        f"<span class='tag-pill'>{l}</span>" for l in labels
    )
    st.markdown(f"<div>{pills}</div>", unsafe_allow_html=True)


def section_label(text: str):
    st.markdown(
        f"<div class='section-label'>{text}</div>",
        unsafe_allow_html=True,
    )


def status_ok(msg: str):
    st.markdown(
        f"<p style='font-size:0.82rem;color:#2e7d32;font-family:IBM Plex Mono,monospace'>✔ {msg}</p>",
        unsafe_allow_html=True,
    )


def status_warn(msg: str):
    st.markdown(
        f"<p style='font-size:0.82rem;color:#b45309;font-family:IBM Plex Mono,monospace'>⚠ {msg}</p>",
        unsafe_allow_html=True,
    )


def status_error(msg: str):
    st.markdown(
        f"<p style='font-size:0.82rem;color:#c62828;font-family:IBM Plex Mono,monospace'>✘ {msg}</p>",
        unsafe_allow_html=True,
    )


def file_card(name: str, file_type: str, fmt: str, size_kb: float, metadata: dict = {}):
    with st.container(border=True):
        col_a, col_b = st.columns([3, 1])
        with col_a:
            st.markdown(
                f"<span style='font-family:IBM Plex Mono,monospace;font-size:0.85rem;font-weight:600'>{name}</span>",
                unsafe_allow_html=True,
            )
            tag_row([file_type, fmt])
        with col_b:
            st.markdown(
                f"<p style='font-size:0.78rem;color:#aaa;text-align:right;font-family:IBM Plex Mono,monospace'>{size_kb:.1f} KB</p>",
                unsafe_allow_html=True,
            )
        if metadata:
            with st.expander("Metadata", expanded=False):
                st.json(metadata)


def progress_log(messages: list[str]):
    with st.container(border=True):
        section_label("Agent Log")
        for msg in messages:
            st.markdown(
                f"<p style='font-family:IBM Plex Mono,monospace;font-size:0.78rem;color:#555;margin:0.1rem 0'>{msg}</p>",
                unsafe_allow_html=True,
            )


def api_key_guard() -> bool:
    if not st.session_state.get("openai_api_key"):
        st.info("Enter your OpenAI API key in the sidebar to use this feature.")
        return False
    return True


def empty_state(icon: str, message: str):
    st.markdown(
        f"""
        <div style='text-align:center;padding:3rem 1rem;color:#aaa'>
            <div style='font-size:2.5rem'>{icon}</div>
            <p style='font-family:IBM Plex Mono,monospace;font-size:0.82rem;margin-top:0.8rem'>{message}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def two_col(ratio: tuple[int, int] = (1, 1)):
    return st.columns(ratio)


def divider_label(text: str):
    st.markdown(
        f"<div style='display:flex;align-items:center;gap:0.8rem;margin:1rem 0'>"
        f"<div style='flex:1;height:1px;background:#e5e5e0'></div>"
        f"<span style='font-family:IBM Plex Mono,monospace;font-size:0.68rem;color:#aaa;letter-spacing:0.08em;text-transform:uppercase'>{text}</span>"
        f"<div style='flex:1;height:1px;background:#e5e5e0'></div>"
        f"</div>",
        unsafe_allow_html=True,
    )