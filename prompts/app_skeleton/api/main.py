# api/main.py
# Drop this alongside your existing agents/, core/, prompts/, tools/, config.py.
# Those directories are imported unmodified -- this file is the ONLY new thing
# that talks HTTP; everything it calls into already exists in your repo.

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routes import analyze, chat, report

app = FastAPI(title="Engineering Assistant API")

# During local dev, the Next.js frontend runs on a different port, so CORS must be
# explicitly allowed. Tighten this to your actual frontend origin before deploying
# to a customer -- "*" is fine for testing today only.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analyze.router, prefix="/api/analyze", tags=["analyze"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(report.router, prefix="/api/report", tags=["report"])


@app.get("/api/health")
def health():
    return {"status": "ok"}

# Run with: uvicorn api.main:app --reload --port 8000
