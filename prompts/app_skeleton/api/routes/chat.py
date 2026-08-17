# api/routes/chat.py
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

import config
from agents.query_agent import QueryAgent

router = APIRouter()


class ChatRequest(BaseModel):
    message: str


@router.post("")
def chat(req: ChatRequest):
    """Wraps the existing QueryAgent -- same natural-language search your
    query_ui.py already calls, just exposed as a plain JSON endpoint for now.
    Add SSE streaming here the same way as analyze.py once this is working."""
    agent = QueryAgent(model=config.AGENT_MODEL)
    result = agent.run(req.message)
    return result
