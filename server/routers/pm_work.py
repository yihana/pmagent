# server/routers/pm_work.py
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

# DB 세션 (필요 시 사용)
from server.db.database import get_db  # SessionLocal 의존성
from sqlalchemy.orm import Session

# PM 그래프 파이프라인 (기존 코드 호환)
from server.workflow.pm_graph import run_pipeline

router = APIRouter(prefix="/api/v1/pm", tags=["pm"])

# =========================
# 요청/응답 모델
# =========================

class AnalyzeRequest(BaseModel):
    project_id: str | int = Field(..., description="프로젝트 ID")
    doc_type: Optional[str] = Field(default="meeting", description="문서 유형 (meeting, report, issue 등)")
    title: Optional[str] = Field(default=None, description="문서 제목")
    text: str = Field(..., description="분석할 원문 텍스트")
    enable_rag: Optional[bool] = Field(default=True, description="RAG 사용 여부")

class AnalyzeResponse(BaseModel):
    status: str = "ok"
    data: Dict[str, Any] | list | None = None
    message: Optional[str] = None

class ReportResponse(BaseModel):
    status: str = "ok"
    data: Dict[str, Any] | list | None = None
    message: Optional[str] = None


# =========================
# 유틸
# =========================

def _to_int(x: str | int) -> int:
    try:
        return int(x)
    except Exception:
        raise HTTPException(400, detail=f"project_id must be an integer: got {x!r}")

def _parse_ymd(s: str) -> date:
    try:
        # YYYY-MM-DD 포맷 권장
        return date.fromisoformat(s)
    except Exception:
        # 여유 파서 (YYYY/MM/DD 등) — 필요 없으면 제거 가능
        try:
            return datetime.strptime(s, "%Y/%m/%d").date()
        except Exception:
            raise HTTPException(400, detail=f"Invalid date format: {s!r}. Use YYYY-MM-DD.")

def _this_week() -> tuple[date, date]:
    """이번 주(월~일) 기본 구간"""
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    return monday, sunday


# =========================
# 라우트
# =========================

@router.post("/graph/analyze", response_model=AnalyzeResponse)
async def graph_analyze(
    body: AnalyzeRequest,
    db: Session = Depends(get_db),
):
    """
    문서 인제스트 + 분석 실행.
    기존 pm_graph.run_pipeline("analyze", payload) 흐름을 그대로 사용합니다.
    """
    project_id = _to_int(body.project_id)

    payload = {
        "project_id": project_id,
        "doc_type": body.doc_type or "meeting",
        "title": body.title or "",
        "text": body.text,
        "enable_rag": bool(body.enable_rag),
    }

    try:
        # pm_graph 내부에서 ANALYZER 노드 구성 → PM_AnalyzerAgent 호출
        res = await run_pipeline("analyze", payload)
        return AnalyzeResponse(status="ok", data=res)
    except HTTPException:
        raise
    except Exception as e:
        # 상세 오류 노출(개발 단계)
        raise HTTPException(500, detail=f"analyze failed: {e}")


@router.get("/graph/report", response_model=ReportResponse)
async def graph_report(
    project_id: str = Query(..., description="프로젝트 ID"),
    week_start: Optional[str] = Query(None, description="리포트 시작일(YYYY-MM-DD)"),
    week_end: Optional[str] = Query(None, description="리포트 종료일(YYYY-MM-DD)"),
    db: Session = Depends(get_db),
):
    """
    분석 결과 기반 리포트 조회.
    - week_start/week_end 가 없으면 '이번 주(월~일)'로 기본값 적용
    """
    pid = _to_int(project_id)

    if week_start and week_end:
        start_d = _parse_ymd(week_start)
        end_d = _parse_ymd(week_end)
        if start_d > end_d:
            raise HTTPException(400, detail="week_start must be <= week_end")
    else:
        start_d, end_d = _this_week()

    payload = {
        "project_id": pid,
        "week_start": start_d.isoformat(),
        "week_end": end_d.isoformat(),
    }

    try:
        res = await run_pipeline("report", payload)
        return ReportResponse(status="ok", data=res)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, detail=f"report failed: {e}")
