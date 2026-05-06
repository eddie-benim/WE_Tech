import streamlit as st
import os
from pathlib import Path

import config
from ui.report_ui import render_report_tab
from ui.file_ui import render_file_tab
from ui.library_ui import render_library_tab

st.set_page_config(
    page_title=config.APP_TITLE,
    page_icon=config.APP_ICON,
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;600&display=swap');

    html, body, [class*="css"] {
        font-family: 'IBM Plex Sans', sans-serif;
    }

    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }

    h1, h2, h3 {
        font-family: 'IBM Plex Mono', monospace;
        letter-spacing: -0.02em;
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 0px;
        border-bottom: 2px solid #e0e0e0;
    }

    .stTabs [data-baseweb="tab"] {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.82rem;
        font-weight: 600;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        padding: 0.6rem 1.4rem;
        border-radius: 0;
        color: #888;
        background: transparent;
        border: none;
    }

    .stTabs [aria-selected="true"] {
        color: #1a1a1a;
        border-bottom: 2px solid #1a1a1a;
        background: transparent;
    }

    .stSidebar {
        background-color: #f7f7f5;
        border-right: 1px solid #e5e5e0;
    }

    .stButton > button {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.78rem;
        font-weight: 600;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        border-radius: 2px;
        border: 1.5px solid #1a1a1a;
        background: #1a1a1a;
        color: #ffffff;
        padding: 0.5rem 1.2rem;
        transition: all 0.15s ease;
    }

    .stButton > button:hover {
        background: #ffffff;
        color: #1a1a1a;
    }

    .stTextInput > div > div > input,
    .stTextArea > div > div > textarea,
    .stSelectbox > div > div {
        font-family: 'IBM Plex Sans', sans-serif;
        border-radius: 2px;
        border: 1.5px solid #d0d0cc;
        font-size: 0.9rem;
    }

    .status-bar {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.72rem;
        color: #888;
        letter-spacing: 0.05em;
        padding: 0.3rem 0;
        border-top: 1px solid #e5e5e0;
        margin-top: 1rem;
    }

    .tag-pill {
        display: inline-block;
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.68rem;
        font-weight: 600;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        padding: 0.18rem 0.6rem;
        border-radius: 2px;
        background: #f0f0ec;
        border: 1px solid #d0d0cc;
        color: #444;
        margin: 0.1rem;
    }

    .section-label {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.7rem;
        font-weight: 600;
        letter-spacing: 0.1em;
        text-transform: uppercase;
        color: #aaa;
        margin-bottom: 0.4rem;
    }

    div[data-testid="stFileUploader"] {
        border: 1.5px dashed #c0c0bc;
        border-radius: 4px;
        padding: 0.5rem;
        background: #fafaf8;
    }
</style>
""", unsafe_allow_html=True)


def render_sidebar():
    with st.sidebar:
        st.markdown(f"## {config.APP_ICON} {config.APP_TITLE}")
        st.markdown(f"<p style='font-size:0.82rem;color:#888;margin-top:-0.5rem'>{config.APP_SUBTITLE}</p>", unsafe_allow_html=True)
        st.divider()

        api_key = st.text_input(
            "OpenAI API Key",
            value=st.session_state.get("openai_api_key", config.OPENAI_API_KEY),
            type="password",
            placeholder="sk-...",
            help="Your key is stored only in this session and never written to disk.",
        )

        if api_key:
            st.session_state["openai_api_key"] = api_key
            os.environ["OPENAI_API_KEY"] = api_key

        st.divider()

        st.markdown("<div class='section-label'>Reference Library</div>", unsafe_allow_html=True)

        ref_count = len(list(config.COMPANY_FILES_DIR.rglob("*")))
        file_count = len([f for f in config.COMPANY_FILES_DIR.rglob("*") if f.is_file()])
        st.markdown(f"<p style='font-size:0.82rem;color:#555'>{file_count} file(s) indexed</p>", unsafe_allow_html=True)

        st.divider()

        st.markdown("<div class='section-label'>Model</div>", unsafe_allow_html=True)
        model_choice = st.selectbox(
            "Agent model",
            options=["gpt-4o", "gpt-4o-mini"],
            index=0,
            label_visibility="collapsed",
        )
        st.session_state["agent_model"] = model_choice

        st.divider()

        if st.button("⚙ Debug config"):
            st.session_state["show_debug"] = not st.session_state.get("show_debug", False)

        if st.session_state.get("show_debug", False):
            st.json(config.as_dict())

        st.markdown(
            "<div class='status-bar'>Engineering Assistant · v0.1.0</div>",
            unsafe_allow_html=True,
        )


def main():
    render_sidebar()

    st.markdown("# Engineering Assistant")
    st.markdown(
        "<p style='font-size:0.95rem;color:#666;margin-top:-0.8rem;margin-bottom:1.5rem'>"
        "Upload reference documents via the <b>Reference Library</b> tab first, "
        "then use the other tools."
        "</p>",
        unsafe_allow_html=True,
    )

    tab_report, tab_files, tab_library = st.tabs(config.NAV_TABS)

    with tab_report:
        render_report_tab()

    with tab_files:
        render_file_tab()

    with tab_library:
        render_library_tab()


if __name__ == "__main__":
    main()