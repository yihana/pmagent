# server/routers/pm_agent.py
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import date
from server.db.database import get_db
from server.workflow.pm_graph import run_pipeline

router = APIRouter(prefix="/api/v1/pm", tags=["pm"])

class AnalyzeIn(BaseModel):
    project_id: int
    doc_type: str = "meeting"
    title: str
    text: str

@router.post("/graph/analyze")
async def graph_analyze(payload: AnalyzeIn, db: Session = Depends(get_db)):
    res = await run_pipeline("analyze", {
        "db": db,
        "project_id": payload.project_id,
        "doc_type": payload.doc_type,
        "title": payload.title,
        "text": payload.text
    })
    return res

@router.get("/graph/report")
async def graph_report(project_id: int, week_start: str, week_end: str, db: Session = Depends(get_db)):
    res = await run_pipeline("report", {
        "db": db,
        "project_id": project_id,
        "doc_type": "meeting",
        "title": f"auto-{week_start}",
        "text": "",  # 분석 입력이 없으면 risk 노드에서 최근 액션을 fallback
        "week_start": week_start,
        "week_end": week_end
    })
    return res
