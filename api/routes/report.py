# api/routes/report.py
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

import config
from agents.report_agent import ReportAgent

router = APIRouter()


class ReportRequest(BaseModel):
    report_type: str
    project_info: dict
    use_web_search: bool = True


@router.post("")
def generate_report(req: ReportRequest):
    agent = ReportAgent(model=config.AGENT_MODEL)
    return agent.run(
        report_type=req.report_type,
        project_info=req.project_info,
        use_web_search=req.use_web_search,
    )
