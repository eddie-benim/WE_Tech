from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

ROOT_DIR: Path = Path(__file__).parent.resolve()


DATA_DIR:         Path = ROOT_DIR / "data"
COMPANY_FILES_DIR: Path = DATA_DIR / "company_files"   
OUTPUTS_DIR:      Path = DATA_DIR / "outputs"         
VECTOR_STORE_DIR: Path = DATA_DIR / "vector_store"     

PROMPTS_DIR: Path = ROOT_DIR / "prompts"

for _d in (COMPANY_FILES_DIR, OUTPUTS_DIR, VECTOR_STORE_DIR):
    _d.mkdir(parents=True, exist_ok=True)

OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

if not OPENAI_API_KEY:
    import warnings
    warnings.warn(
        "OPENAI_API_KEY is not set. "
        "Add it to a .env file or export it in your shell before launching.",
        stacklevel=1,
    )

AGENT_MODEL: str = os.getenv("AGENT_MODEL", "gpt-4o")

FAST_MODEL: str = os.getenv("FAST_MODEL", "gpt-4o-mini")

EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

MAX_COMPLETION_TOKENS: int = int(os.getenv("MAX_COMPLETION_TOKENS", "4096"))

TOP_K_RETRIEVAL: int = int(os.getenv("TOP_K_RETRIEVAL", "8"))

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
    "Report":               ["report"],         
}

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

REPORT_TYPES: list[str] = [
    "Heat & Energy Balance Report",
    "Equipment Sizing Report",
    "Project Proposal",
    "General Technical Report",
]

MAX_REFERENCE_DOCS: int = int(os.getenv("MAX_REFERENCE_DOCS", "5"))

REFERENCE_TOKEN_BUDGET: int = int(os.getenv("REFERENCE_TOKEN_BUDGET", "6000"))

NAMING_SEPARATOR: str = "_"

DEFAULT_REVISION: str = "Rev0"

MAX_FILENAME_LENGTH: int = 80

CHROMA_COLLECTION_COMPANY: str = "company_references"
CHROMA_COLLECTION_METADATA: str = "file_metadata"

CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "1200"))
CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "200"))

APP_TITLE:    str = "Engineering Assistant"
APP_ICON:     str = "⚙️"
APP_SUBTITLE: str = "AI-powered workflow tools for process engineers"

NAV_TABS: list[str] = [
    "📄 Report Generator",
    "🗂️ File Organiser",
    "📚 Reference Library",
]

LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

def as_dict() -> dict:
    """Return a snapshot of all public config values (useful for debug UI)."""
    import inspect
    return {
        k: str(v)
        for k, v in globals().items()
        if not k.startswith("_") and not inspect.ismodule(v) and not callable(v)
    }