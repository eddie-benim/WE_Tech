# api/routes/analyze.py
from __future__ import annotations

import asyncio
import json
import shutil
import threading
from pathlib import Path

from fastapi import APIRouter, UploadFile, File
from fastapi.responses import StreamingResponse

import config
from agents.file_agent import FileAgent

router = APIRouter()

STAGING_DIR = config.DATA_DIR / "staging"
STAGING_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/stream")
async def analyze_stream(files: list[UploadFile] = File(...)):
    """Streams progress lines live as the existing FileAgent runs, then a final
    'result' event with the full structured output -- same data your Streamlit
    file_ui.py already renders, just delivered over SSE instead of a page rerun.
    """
    staged_paths: list[Path] = []
    for f in files:
        dest = STAGING_DIR / f.filename
        with dest.open("wb") as out:
            shutil.copyfileobj(f.file, out)
        staged_paths.append(dest)

    agent = FileAgent(model=config.AGENT_MODEL)
    result_holder: dict = {}
    done = threading.Event()

    def run_agent():
        try:
            result_holder["results"] = agent.analyze_files(staged_paths)
        except Exception as e:
            result_holder["error"] = str(e)
        finally:
            done.set()

    threading.Thread(target=run_agent, daemon=True).start()

    async def event_stream():
        sent = 0
        while not done.is_set() or sent < len(agent.log):
            while sent < len(agent.log):
                yield f"event: log\ndata: {json.dumps(agent.log[sent])}\n\n"
                sent += 1
            await asyncio.sleep(0.15)  # simple polling cadence -- fine for v1

        if "error" in result_holder:
            yield f"event: error\ndata: {json.dumps(result_holder['error'])}\n\n"
        else:
            yield f"event: result\ndata: {json.dumps(result_holder['results'])}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
