"""
config.py
─────────────────────────────────────────────────────────────────────────────
Central configuration for the Engineering Assistant.

All tunable knobs, path constants, and environment-variable loading live here.
Nothing in this file calls OpenAI or performs I/O beyond reading .env.
─────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

# ── Load .env (if present) ────────────────────────────────────────────────────
load_dotenv()


# ═══════════════════════════════════════════════════════════════════════════════
# 1.  PATHS
# ═══════════════════════════════════════════════════════════════════════════════

# Root of the project (directory that contains config.py)
ROOT_DIR: Path = Path(__file__).parent.resolve()

# Persistent data directories
DATA_DIR:         Path = ROOT_DIR / "data"
COMPANY_FILES_DIR: Path = DATA_DIR / "company_files"   # uploaded reference docs
OUTPUTS_DIR:      Path = DATA_DIR / "outputs"           # generated reports / organised files
VECTOR_STORE_DIR: Path = DATA_DIR / "vector_store"      # ChromaDB persistence

# Prompt modules live here (imported by agents, not file paths per se)
PROMPTS_DIR: Path = ROOT_DIR / "prompts"

# Ensure all directories exist at import time so the rest of the app
# never has to worry about missing folders.
for _d in (COMPANY_FILES_DIR, OUTPUTS_DIR, VECTOR_STORE_DIR):
    _d.mkdir(parents=True, exist_ok=True)


# ═══════════════════════════════════════════════════════════════════════════════
# 2.  API KEYS  (read from environment / .env)
# ═══════════════════════════════════════════════════════════════════════════════

OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

if not OPENAI_API_KEY:
    import warnings
    warnings.warn(
        "OPENAI_API_KEY is not set. "
        "Add it to a .env file or export it in your shell before launching.",
        stacklevel=1,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 3.  MODEL SETTINGS
# ═══════════════════════════════════════════════════════════════════════════════

# Primary model used by all agents
AGENT_MODEL: str = os.getenv("AGENT_MODEL", "gpt-4o")

# Cheaper / faster model for lightweight tasks (classification, short summaries)
FAST_MODEL: str = os.getenv("FAST_MODEL", "gpt-4o-mini")

# Embedding model for ChromaDB vector store
EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

# Max tokens the agent may emit in a single completion
MAX_COMPLETION_TOKENS: int = int(os.getenv("MAX_COMPLETION_TOKENS", "4096"))

# How many reference document chunks to retrieve from the vector store
#   when building agent context
TOP_K_RETRIEVAL: int = int(os.getenv("TOP_K_RETRIEVAL", "8"))


# ═══════════════════════════════════════════════════════════════════════════════
# 4.  FILE-CLASSIFIER SETTINGS  (rule-based, no AI)
# ═══════════════════════════════════════════════════════════════════════════════

# Maps canonical document-type labels → keyword signals found in filenames
# or first-page text.  Order matters: first match wins.
FILE_TYPE_KEYWORDS: dict[str, list[str]] = {
    "PFD":                  ["pfd", "process flow diagram", "process flow"],
    "P&ID":                 ["p&id", "pid", "piping and instrumentation", "piping & instrumentation"],
    "Heat & Energy Balance":["heat balance", "energy balance", "h&eb", "heb", "heat and energy"],
    "Equipment Sizing":     ["equipment sizing", "sizing report", "equipment spec"],
    "Proposal":             ["proposal", "project proposal", "scope of work", "sow"],
    "Data Sheet":           ["data sheet", "datasheet", "spec sheet"],
    "Isometric":            ["isometric", "iso drawing"],
    "GA Drawing":           ["general arrangement", "ga drawing", " ga "],
    "Cause & Effect":       ["cause and effect", "cause & effect", "c&e matrix"],
    "Hazop":                ["hazop", "hazard and operability"],
    "Report":               ["report"],          # generic fallback
}

# Supported ingest extensions → human-readable format label
SUPPORTED_EXTENSIONS: dict[str, str] = {
    ".pdf":  "PDF",
    ".png":  "PNG Image",
    ".jpg":  "JPEG Image",
    ".jpeg": "JPEG Image",
    ".docx": "Word Document",
    ".doc":  "Word Document",
    ".xlsx": "Excel Spreadsheet",
    ".xls":  "Excel Spreadsheet",
    ".pptx": "PowerPoint",
    ".ppt":  "PowerPoint",
    ".txt":  "Plain Text",
}


# ═══════════════════════════════════════════════════════════════════════════════
# 5.  REPORT-GENERATION SETTINGS
# ═══════════════════════════════════════════════════════════════════════════════

# Report types the UI will offer in the dropdown
REPORT_TYPES: list[str] = [
    "Heat & Energy Balance Report",
    "Equipment Sizing Report",
    "Project Proposal",
    "General Technical Report",
]

# How many company reference documents to surface per report type
MAX_REFERENCE_DOCS: int = int(os.getenv("MAX_REFERENCE_DOCS", "5"))

# Token budget reserved for injected reference content inside the prompt
REFERENCE_TOKEN_BUDGET: int = int(os.getenv("REFERENCE_TOKEN_BUDGET", "6000"))


# ═══════════════════════════════════════════════════════════════════════════════
# 6.  FILE-ORGANISER SETTINGS
# ═══════════════════════════════════════════════════════════════════════════════

# Separator used when building machine-friendly filenames
#   e.g.  PRJ-001_PFD_Separation-Train_Rev0.pdf
NAMING_SEPARATOR: str = "_"

# Default revision token appended when no revision is detected
DEFAULT_REVISION: str = "Rev0"

# Maximum characters allowed in a generated filename (before extension)
MAX_FILENAME_LENGTH: int = 80


# ═══════════════════════════════════════════════════════════════════════════════
# 7.  VECTOR STORE / CHROMADB SETTINGS
# ═══════════════════════════════════════════════════════════════════════════════

CHROMA_COLLECTION_COMPANY: str = "company_references"
CHROMA_COLLECTION_METADATA: str = "file_metadata"

# Chunk size (characters) when splitting documents for embedding
CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "1200"))
CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "200"))


# ═══════════════════════════════════════════════════════════════════════════════
# 8.  STREAMLIT UI SETTINGS
# ═══════════════════════════════════════════════════════════════════════════════

APP_TITLE:    str = "Engineering Assistant"
APP_ICON:     str = "⚙️"
APP_SUBTITLE: str = "AI-powered workflow tools for process engineers"

# Tabs shown in the sidebar / main nav
NAV_TABS: list[str] = [
    "🔍 Document Search",
    "📄 Report Generator",
    "🗂️ File Organiser",
    "📚 Reference Library",
]


# ═══════════════════════════════════════════════════════════════════════════════
# 9.  LOGGING
# ═══════════════════════════════════════════════════════════════════════════════

LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")


# ── Convenience helper ────────────────────────────────────────────────────────

def as_dict() -> dict:
    """Return a snapshot of all public config values (useful for debug UI)."""
    import inspect
    return {
        k: str(v)
        for k, v in globals().items()
        if not k.startswith("_") and not inspect.ismodule(v) and not callable(v)
    }
