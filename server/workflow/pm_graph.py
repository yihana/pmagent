# server/workflow/pm_graph.py
from __future__ import annotations
import asyncio
from datetime import datetime, date
from typing import Any, Dict, List, Optional, Union
import logging
from pathlib import Path

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger("pm.graph")

# DB / 모델 import
try:
    from server.db.database import SessionLocal
    from server.db import pm_models
    _DB_AVAILABLE = True
except Exception as e:
    logger.warning("[DB] import failed: %s", e)
    SessionLocal = None
    pm_models = None
    _DB_AVAILABLE = False

# Analyzer / Report 모듈 import
try:
    from server.workflow.agents.pm_report import build_weekly_report
    _REPORT_AVAILABLE = True
except Exception as e:
    logger.warning("[REPORT] import failed: %s", e)
    def build_weekly_report(db: Session, project_id: int) -> Dict[str, Any]:
        return {"project_id": project_id, "summary": "report module not found"}
    _REPORT_AVAILABLE = False

try:
    from server.workflow.agents import analyzer
    _ANALYZER_AVAILABLE = True
except Exception as e:
    logger.warning("[ANALYZER] import failed: %s", e)
    analyzer = None
    _ANALYZER_AVAILABLE = False

# Scope Agent import
try:
    from server.workflow.agents.scope_agent.pipeline import ScopeAgent
    _SCOPE_AVAILABLE = True
except Exception as e:
    logger.warning("[SCOPE_AGENT] import failed: %s", e)
    ScopeAgent = None
    _SCOPE_AVAILABLE = False

# Schedule Agent import
try:
    from server.workflow.agents.schedule_agent.pipeline import ScheduleAgent
    _SCHEDULE_AVAILABLE = True
except Exception as e:
    logger.warning("[SCHEDULE_AGENT] import failed: %s", e)
    ScheduleAgent = None
    _SCHEDULE_AVAILABLE = False


# ===============================
#  공용 유틸
# ===============================
ANALYZE_TIMEOUT_SEC = 30

def _resolve_data_dir() -> Path:
    """프로젝트 루트의 data 폴더 찾기"""
    here = Path(__file__).resolve()
    for p in here.parents:
        if (p / "data").exists():
            return p / "data"
    return here.parents[1] / "data"

DATA_DIR = _resolve_data_dir()

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

def _to_dict(obj: Any) -> Dict[str, Any]:
    """Pydantic BaseModel 등 어떤 형태든 안전하게 dict로 표준화"""
    if isinstance(obj, dict):
        return obj
    # Pydantic v2
    md = getattr(obj, "model_dump", None)
    if callable(md):
        try:
            return md()
        except Exception:
            pass
    # Pydantic v1
    dct = getattr(obj, "dict", None)
    if callable(dct):
        try:
            return dct()
        except Exception:
            pass
    # 일반 객체
    try:
        return dict(obj)
    except Exception:
        return {"value": obj}


# ===============================
#  Analyzer 실행 가드
# ===============================
async def _run_analyzer_with_timeout(text: str, project_id: int) -> List[Dict[str, Any]]:
    """analyzer.analyze_minutes() 실행을 timeout-safe로 감싸는 함수"""
    if not (_ANALYZER_AVAILABLE and analyzer and hasattr(analyzer, "analyze_minutes")):
        logger.info("[ANALYZER] module not found; skip")
        return []

    def _call():
        return analyzer.analyze_minutes(text, project_meta={"project_id": project_id})

    try:
        raw = await asyncio.wait_for(asyncio.to_thread(_call), timeout=ANALYZE_TIMEOUT_SEC)
    except asyncio.TimeoutError:
        logger.warning(f"[ANALYZER] timeout after {ANALYZE_TIMEOUT_SEC}s; skip items")
        return []
    except Exception as e:
        logger.exception(f"[ANALYZER] failed: {e!r}")
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
        elif kind == "scope":
            self.handler = _scope_handler
        elif kind == "scope_summary":
            self.handler = _scope_summary_handler
        elif kind == "schedule":
            self.handler = _schedule_handler
        elif kind == "schedule_timeline":
            self.handler = _schedule_timeline_handler
        elif kind == "workflow_scope_then_schedule":
            self.handler = _workflow_scope_then_schedule_handler
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

    if not _DB_AVAILABLE:
        logger.warning("[ANALYZE] DB not available; returning minimal result")
        return {
            "ok": True,
            "document_id": None,
            "doc_type": doc_type,
            "saved_action_items": 0,
            "note": "DB not available"
        }

    db: Session = SessionLocal()
    try:
        # 1) 문서 저장
        doc = pm_models.PM_Document(
            project_id=project_id,
            title=title,
            content=text,
            doc_type=doc_type,
            created_at=_utcnow(),
        )
        db.add(doc)
        db.flush()

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
                logger.warning(f"[ANALYZER] skip item #{idx} due to {e!r}")

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

    if not _DB_AVAILABLE:
        logger.warning("[REPORT] DB not available; returning minimal report")
        return {
            "ok": True,
            "project_id": project_id,
            "report": {"summary": "DB not available"}
        }

    db: Session = SessionLocal()
    try:
        report = build_weekly_report(db, project_id)
        return {"ok": True, "project_id": project_id, "report": report}
    except Exception as e:
        raise RuntimeError(f"report failed: {e}")
    finally:
        db.close()


# ===============================
#  Scope 핸들러
# ===============================
async def _scope_handler(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    입력:
      {
        "project_id": "default",
        "project_name": "Demo Project",
        "methodology": "waterfall",
        "documents": [{"path": "data/inputs/RFP/sample.pdf", "type": "RFP"}],
        "options": {"chunk_size": 500, "overlap": 100}
      }
    출력:
      {
        "project_id": "default",
        "wbs_json_path": "...",
        "rtm_csv_path": "...",
        "scope_md_path": "...",
        "stats": {...}
      }
    """
    if not _SCOPE_AVAILABLE or ScopeAgent is None:
        raise RuntimeError("ScopeAgent not available. Check server/workflow/agents/scope_agent/pipeline.py")

    agent = ScopeAgent(data_dir=str(DATA_DIR))
    
    # ScopeAgent.pipeline()은 이미 비동기 함수
    result = await agent.pipeline(payload)
    
    return result


async def _scope_summary_handler(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Scope 결과 요약 조회"""
    project_id = payload.get("project_id", "default")
    out_dir = Path(DATA_DIR) / "outputs" / "scope" / str(project_id)
    info = {"project_id": project_id, "exists": out_dir.exists(), "files": []}
    if out_dir.exists():
        for p in sorted(out_dir.glob("*")):
            info["files"].append({"name": p.name, "size": p.stat().st_size})
    return info


# ===============================
#  Schedule 핸들러
# ===============================
async def _schedule_handler(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    입력:
      {
        "project_id": "default",
        "wbs_json": "data/outputs/scope/default/wbs_structure.json",
        "calendar": {"start_date": "2025-11-03", "work_week": [1,2,3,4,5], "holidays": []},
        "resource_pool": [{"role": "PM", "capacity_pct": 80}],
        "sprint_length_weeks": 2,
        "estimation_mode": "llm",
        "methodology": "waterfall"
      }
    출력:
      {
        "plan_csv": "...",
        "gantt_json": "...",
        "critical_path": [...]
      }
    """
    if not _SCHEDULE_AVAILABLE or ScheduleAgent is None:
        logger.warning("[SCHEDULE] ScheduleAgent not available; returning empty schedule")
        return {
            "warn": "ScheduleAgent not available; returning empty schedule",
            "timeline": [],
            "plan_csv": None,
            "gantt_json": None,
            "critical_path": []
        }

    agent = ScheduleAgent(data_dir=str(DATA_DIR))
    result = await agent.pipeline(payload)
    
    return result


async def _schedule_timeline_handler(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Schedule 타임라인 조회"""
    project_id = payload.get("project_id", "default")
    out_dir = Path(DATA_DIR) / "outputs" / "schedule" / str(project_id)
    f = out_dir / "timeline.json"
    if f.exists():
        return {"project_id": project_id, "timeline_path": str(f), "size": f.stat().st_size}
    return {"project_id": project_id, "timeline_path": None}


# ===============================
#  Workflow: Scope -> Schedule
# ===============================
async def _workflow_scope_then_schedule_handler(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    입력:
      {
        "scope": { ... ScopeRequest ... },
        "schedule": { ... ScheduleRequest ... }
      }
    OR 단순 payload (scope와 schedule을 자동 구성)
    출력:
      {
        "scope": { ... scope 결과 ... },
        "schedule": { ... schedule 결과 ... }
      }
    """
    # 방법 1: scope/schedule이 명시적으로 분리된 경우
    if "scope" in payload and "schedule" in payload:
        scope_payload = payload["scope"]
        schedule_payload = payload["schedule"]
        
        # Scope 실행
        scope_result = await _scope_handler(scope_payload)
        
        # WBS 경로를 Schedule payload에 자동 주입
        wbs_json_path = scope_result.get("wbs_json_path")
        if wbs_json_path:
            schedule_payload["wbs_json"] = wbs_json_path
        
        # Schedule 실행
        schedule_result = await _schedule_handler(schedule_payload)
        
        return {
            "scope": scope_result,
            "schedule": schedule_result
        }
    
    # 방법 2: 단순 payload (Scope만 실행하고 Schedule은 준비)
    else:
        scope_result = await _scope_handler(payload)
        wbs_json_path = scope_result.get("wbs_json_path")
        
        # Schedule payload 자동 구성
        sched_payload = {
            "project_id": payload.get("project_id", "default"),
            "wbs_json": wbs_json_path
        }
        
        schedule_result = await _schedule_handler(sched_payload)
        
        return {
            "scope": scope_result,
            "schedule": schedule_result
        }


# ===============================
#  파이프라인 실행 진입점
# ===============================
async def run_pipeline(kind: str, payload: Any) -> Dict[str, Any]:
    """
    진입부에서 payload 표준화:
    - 대시보드/라우터에서 Pydantic 모델이 전달되든, dict이든, 항상 dict로 변환
    - 여기서 변환해두면 하위 핸들러/에이전트에서 .get 사용해도 안전
    """
    norm = _to_dict(payload)
    app = _App(kind)
    return await app.ainvoke(norm)