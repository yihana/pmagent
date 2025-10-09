from __future__ import annotations
import asyncio
from datetime import datetime, date
from typing import Any, Dict, List, Optional, Union

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

# DB / 모델 import
from server.db.database import SessionLocal
from server.db import pm_models

# -----------------------------
# Analyzer / Report 모듈 import
# -----------------------------
try:
    from server.workflow.agents.pm_report import build_weekly_report  # type: ignore
except Exception:
    def build_weekly_report(db: Session, project_id: int) -> Dict[str, Any]:
        return {"project_id": project_id, "summary": "report module not found"}

try:
    from server.workflow.agents import analyzer  # type: ignore
except Exception:
    analyzer = None


# ===============================
#  공통 유틸
# ===============================
ANALYZE_TIMEOUT_SEC = 30  # 분석기 최대 대기 시간(초)

def _utcnow() -> datetime:
    return datetime.utcnow().replace(microsecond=0)

def _to_date(v: Optional[Union[str, date]]) -> Optional[date]:
    if v is None or isinstance(v, date):
        return v
    s = str(v).strip()
    if not s:
        return None
    try:
        y, m, d = s.split("-")
        return date(int(y), int(m), int(d))
    except Exception:
        return None


# ===============================
#  Analyzer 실행 가드
# ===============================
async def _run_analyzer_with_timeout(text: str, project_id: int) -> List[Dict[str, Any]]:
    """analyzer.analyze_minutes() 실행을 timeout-safe로 감싸는 함수"""
    if not (analyzer and hasattr(analyzer, "analyze_minutes")):
        print("[ANALYZER] module not found; skip")
        return []

    def _call():
        return analyzer.analyze_minutes(text, project_meta={"project_id": project_id})

    try:
        raw = await asyncio.wait_for(asyncio.to_thread(_call), timeout=ANALYZE_TIMEOUT_SEC)
    except asyncio.TimeoutError:
        print(f"[ANALYZER] timeout after {ANALYZE_TIMEOUT_SEC}s; skip items")
        return []
    except Exception as e:
        print(f"[ANALYZER] failed: {e!r}")
        return []

    items = raw.get("items") if isinstance(raw, dict) and "items" in raw else raw
    return items if isinstance(items, list) else []


# ===============================
#  파이프라인 컨테이너
# ===============================
class _App:
    def __init__(self, kind: str):
        self.kind = kind
        if kind == "analyze":
            self.handler = _analyze_handler
        elif kind == "report":
            self.handler = _report_handler
        else:
            raise ValueError(f"unknown pipeline kind: {kind}")

    async def ainvoke(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return await self.handler(payload)


# ===============================
#  분석 핸들러
# ===============================
async def _analyze_handler(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    입력:
      {
        "project_id": 1001,
        "doc_type": "meeting" | "report" | "issue",
        "title": "문서 제목",
        "text": "분석대상 원문"
      }
    출력: {ok, document_id, saved_action_items, ...}
    """
    project_id = int(payload.get("project_id") or 0)
    doc_type: str = (payload.get("doc_type") or "meeting").strip()
    title: str = (payload.get("title") or "Untitled").strip()
    text: str = payload.get("text") or ""

    if not project_id:
        raise ValueError("project_id is required")
    if not text.strip():
        raise ValueError("text is empty")

    db: Session = SessionLocal()
    try:
        # 1) 문서 저장
        doc = pm_models.PM_Document(
            project_id=project_id,
            title=title,
            content=text,
            doc_type=doc_type,   # ✅ kind 아님
            created_at=_utcnow(),
        )
        db.add(doc)
        db.flush()  # id 확보

        # 2) Analyzer 실행
        raw_items = await _run_analyzer_with_timeout(text, project_id)

        # 3) 액션 아이템 저장
        saved = 0
        for idx, item in enumerate(raw_items or [], start=1):
            try:
                ai = pm_models.PM_ActionItem(
                    project_id=project_id,
                    document_id=doc.id,
                    meeting_id=item.get("meeting_id") if "meeting_id" in item else None,
                    assignee=item.get("assignee"),
                    task=item.get("task") or item.get("title") or "",
                    due_date=_to_date(item.get("due_date")),
                    priority=item.get("priority") or "Medium",
                    status=item.get("status") or "Open",
                    module=item.get("module"),
                    phase=item.get("phase"),
                    evidence_span=item.get("evidence_span"),
                    expected_effort=item.get("expected_effort"),
                    expected_value=item.get("expected_value"),
                    created_at=_utcnow(),
                )
                db.add(ai)
                saved += 1
            except Exception as e:
                print(f"[ANALYZER] skip item #{idx} due to {e!r}")

        db.commit()
        return {
            "ok": True,
            "document_id": doc.id,
            "doc_type": doc_type,
            "saved_action_items": saved,
            "analyzer_timed_out": len(raw_items) == 0,
        }
    except Exception as e:
        db.rollback()
        raise RuntimeError(f"analyze failed: {e}")
    finally:
        db.close()


# ===============================
#  리포트 핸들러
# ===============================
async def _report_handler(payload: Dict[str, Any]) -> Dict[str, Any]:
    project_id = int(payload.get("project_id") or 0)
    if not project_id:
        raise ValueError("project_id is required")

    db: Session = SessionLocal()
    try:
        report = build_weekly_report(db, project_id)
        return {"ok": True, "project_id": project_id, "report": report}
    except Exception as e:
        raise RuntimeError(f"report failed: {e}")
    finally:
        db.close()


# ===============================
#  파이프라인 실행 진입점
# ===============================
async def run_pipeline(kind: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    app = _App(kind)
    return await app.ainvoke(payload)
