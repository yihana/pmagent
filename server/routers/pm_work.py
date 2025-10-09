# server/routers/pm_work.py
from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from server.db.database import get_db
from server.workflow.pm_graph import run_pipeline

router = APIRouter(prefix="/api/v1/pm", tags=["pm"])
log = logging.getLogger("pm.report")

# ===== 공용 모델 =====
class AnalyzeRequest(BaseModel):
    project_id: str | int = Field(..., description="프로젝트 ID")
    doc_type: Optional[str] = Field(default="meeting")
    title: Optional[str] = Field(default=None)
    text: str = Field(..., description="분석 원문")
    enable_rag: Optional[bool] = Field(default=True)

class AnalyzeResponse(BaseModel):
    status: str = "ok"
    data: Dict[str, Any] | list | None = None
    message: Optional[str] = None

class ReportResponse(BaseModel):
    status: str = "ok"
    data: Dict[str, Any] | list | None = None
    message: Optional[str] = None

# ===== 유틸 =====
def _to_int(x: str | int) -> int:
    try:
        return int(x)
    except Exception:
        raise HTTPException(400, detail=f"project_id must be integer: {x!r}")

def _parse_ymd(s: str) -> date:
    try:
        return date.fromisoformat(s)
    except Exception:
        try:
            return datetime.strptime(s, "%Y/%m/%d").date()
        except Exception:
            raise HTTPException(400, detail=f"Invalid date format: {s!r}. Use YYYY-MM-DD.")

def _this_week() -> tuple[date, date]:
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    return monday, sunday

# ===== 라우트 =====
@router.post("/graph/analyze", response_model=AnalyzeResponse)
async def graph_analyze(body: AnalyzeRequest, db: Session = Depends(get_db)):
    project_id = _to_int(body.project_id)

    payload = {
        "project_id": project_id,
        "doc_type": body.doc_type or "meeting",
        "title": body.title or "",
        "text": body.text,
        "enable_rag": bool(body.enable_rag),
        "db": db,  # ✅ 그래프 state로 DB 세션 전달
    }
    log.info(f"[analyze] start pid={payload['project_id']} len={len(payload['text'])}")
    try:
        res = await run_pipeline("analyze", payload)
        log.info("[analyze] done")
        return AnalyzeResponse(status="ok", data=res)
    except HTTPException:
        raise
    except Exception as e:
        log.exception("[analyze] failed")
        raise HTTPException(500, detail=f"analyze failed: {e}")


@router.get("/graph/report", response_model=ReportResponse)
async def graph_report(
    project_id: str = Query(...),
    week_start: Optional[str] = Query(None),
    week_end: Optional[str] = Query(None),
    timeout_s: int = Query(180, description="서버측 실행 타임아웃(초)"),
    fast: bool = Query(False, description="빠른 모드(무거운 단계 생략)"),
    db: Session = Depends(get_db),
):
    """
    주간 리포트: 기간 기본값은 이번 주(월~일).
    """
    pid = _to_int(project_id)

    if week_start and week_end:
        s = _parse_ymd(week_start)
        e = _parse_ymd(week_end)
        if s > e:
            raise HTTPException(400, detail="week_start must be <= week_end")
    else:
        s, e = _this_week()

    payload = {
        "project_id": pid,
        "week_start": s.isoformat(),
        "week_end": e.isoformat(),
        "db": db,
        "fast": fast,
    }

    log.info(f"[report] start pid={pid} {payload['week_start']}~{payload['week_end']} fast={fast} timeout={timeout_s}s")

    try:
        res = await asyncio.wait_for(run_pipeline("report", payload), timeout=timeout_s)
        log.info("[report] done")
        return ReportResponse(status="ok", data=res)
    except asyncio.TimeoutError:
        log.warning("[report] timeout")
        raise HTTPException(status_code=504, detail=f"report timed out (> {timeout_s}s)")
    except HTTPException:
        raise
    except Exception as e:
        log.exception("[report] failed")
        raise HTTPException(500, detail=f"report failed: {e}")
