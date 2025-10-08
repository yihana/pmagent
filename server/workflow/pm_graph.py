# server/workflow/pm_graph.py

"""
pm_graph.py
- PM 분석 파이프라인(분석/리포트)을 단순 래퍼로 구현
- FastAPI 라우터에서 run_pipeline("analyze", payload) 형태로 호출
- LangGraph 없이도 동작하도록 SimpleApp 제공 (ainvoke/stream 시그니처 호환)
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from datetime import datetime, date
from typing import Any, Dict, List, Optional

from server.db.database import SessionLocal
from server.db import pm_models
from server.workflow.agents.pm_analyzer import PM_AnalyzerAgent

log = logging.getLogger(__name__)


# -----------------------------
# 유틸: 날짜/시간 변환 & DB 세션
# -----------------------------
def _to_date(v: Any) -> Optional[date]:
    """문자열 'YYYY-MM-DD'나 'Due: YYYY-MM-DD' 등을 date 객체로 변환. 실패 시 None."""
    if isinstance(v, date):
        return v
    if isinstance(v, str):
        s = v.strip()
        m = re.search(r"\d{4}-\d{2}-\d{2}", s)
        if m:
            try:
                return datetime.strptime(m.group(0), "%Y-%m-%d").date()
            except ValueError:
                return None
    return None


def _utcnow() -> datetime:
    return datetime.utcnow()


class DBSession:
    """with DBSession() as db: 형태로 안전하게 사용"""
    def __enter__(self):
        self.db = SessionLocal()
        return self.db

    def __exit__(self, exc_type, exc, tb):
        try:
            if exc:
                self.db.rollback()
        finally:
            self.db.close()


# -----------------------------
# 간단 앱 래퍼 (LangGraph 대체)
# -----------------------------
@dataclass
class SimpleApp:
    handler: Any  # async function(payload) -> dict

    async def ainvoke(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return await self.handler(payload)

    # stream 호출과의 호환성을 위해 (무시되는 인자 받아도 에러 안 나게)
    def stream(self, payload: Dict[str, Any], *args, **kwargs):
        async def gen():
            result = await self.ainvoke(payload)
            yield {"final": result}
        # 동기 제너레이터로 변환
        loop = asyncio.get_event_loop()
        q: List[Dict[str, Any]] = []

        async def run():
            async for ch in gen():
                q.append(ch)

        loop.run_until_complete(run())
        for ch in q:
            yield ch


# -----------------------------
# ANALYZE 핸들러
# -----------------------------
async def _analyze_handler(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    입력 payload 예:
    {
      "project_id": 1001,
      "text": "... 미팅록 ...",
      "title": "주간 회의(10/06)",
      "doc_type": "meeting",
      "model_name": "gpt-5-nano",      # (선택)
      "temperature": 0                 # (선택)
    }
    """
    project_id: Optional[int] = payload.get("project_id")
    text: str = payload.get("text") or ""
    title: str = payload.get("title") or "Untitled"
    doc_type: str = payload.get("doc_type") or "meeting"

    if not project_id:
        raise ValueError("project_id is required")
    if not text.strip():
        raise ValueError("text is empty")

    # 1) 문서 저장
    with DBSession() as db:
        doc = pm_models.PM_Document(
            project_id=project_id,
            title=title,
            content=text,
            doc_type=doc_type,
            created_at=_utcnow(),
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)

        # 2) 분석 실행
        analyzer = PM_AnalyzerAgent()
        raw = analyzer.analyze_minutes(text, project_meta={"project_id": project_id})

        # 결과 정규화: dict({"items":[...]}) 또는 list([...]) 양쪽 대응
        items = raw.get("items") if isinstance(raw, dict) and "items" in raw else raw or []
        if not isinstance(items, list):
            log.warning("[ANALYZER] items is not a list. raw=%r", raw)
            items = []

        saved: List[int] = []
        skipped: List[str] = []

        for idx, item in enumerate(items, start=1):  # ← 루프 변수 이름 통일
            try:
                ai = pm_models.PM_ActionItem(
                    project_id=project_id,
                    document_id=doc.id,
                    assignee=item.get("assignee"),
                    task=item.get("task"),
                    due_date=_to_date(item.get("due_date")),
                    priority=item.get("priority"),
                    status=item.get("status"),
                    module=item.get("module"),
                    phase=item.get("phase"),
                    evidence_span=item.get("evidence_span"),
                    expected_effort=item.get("expected_effort"),
                    expected_value=item.get("expected_value"),
                    created_at=_utcnow(),
                    # meeting_id=item.get("meeting_id")  # 필요 시 사용
                )
                db.add(ai)
                db.flush()   # id 채우기 위해
                saved.append(ai.id if hasattr(ai, "id") else None)  # None일 수 있으나 로그용
            except Exception as e:
                msg = f"[ANALYZER] skip item #{idx} due to {e!r}"
                log.exception(msg)
                skipped.append(msg)

        db.commit()

        return {
            "ok": True,
            "document_id": doc.id,
            "saved_count": len([i for i in saved if i]),
            "skipped_count": len(skipped),
            "skipped": skipped[:5],  # 너무 길면 일부만
        }


# -----------------------------
# REPORT 핸들러 (스텁)
# -----------------------------
async def _report_handler(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    필요 시 주간 리포트 생성 등 구현.
    현재는 스켈레톤만 제공.
    """
    return {"ok": True, "message": "report handler not implemented yet"}


# -----------------------------
# 그래프/파이프라인 생성 & 실행
# -----------------------------
def create_pm_graph(mode: str) -> SimpleApp:
    mode = (mode or "").lower()
    if mode == "analyze":
        return SimpleApp(handler=_analyze_handler)
    elif mode == "report":
        return SimpleApp(handler=_report_handler)
    else:
        # 기본은 analyze로
        return SimpleApp(handler=_analyze_handler)


async def run_pipeline(mode: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    라우터에서 호출:
      res = await run_pipeline("analyze", payload)
    """
    app = create_pm_graph(mode)
    return await app.ainvoke(payload)
