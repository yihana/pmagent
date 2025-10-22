# server/workflow/pm_graph.py
from __future__ import annotations
import asyncio
from datetime import datetime, date
from typing import Any, Dict, List, Optional, Union, TYPE_CHECKING
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
if TYPE_CHECKING:
    from server.workflow.agents.pm_analyzer import PM_AnalyzerAgent
# Analyzer: PM_AnalyzerAgent 직접 사용
try:
    # Runtime import (inside try/except so server can run when agent isn't available)
    from server.workflow.agents.pm_analyzer import PM_AnalyzerAgent
    _ANALYZER_AGENT_AVAILABLE = True
    _ANALYZER_AGENT_INSTANCE: Optional["PM_AnalyzerAgent"] = None
except Exception as e:
    logger.warning("[PM_ANALYZER] import failed: %s", e)
    PM_AnalyzerAgent = None
    _ANALYZER_AGENT_AVAILABLE = False
    _ANALYZER_AGENT_INSTANCE = None


# Report 모듈 import
try:
    from server.workflow.agents.pm_report import build_weekly_report
    _REPORT_AVAILABLE = True
except Exception as e:
    logger.warning("[REPORT] import failed: %s", e)
    def build_weekly_report(db: Session, project_id: int) -> Dict[str, Any]:
        return {"project_id": project_id, "summary": "report module not found"}
    _REPORT_AVAILABLE = False


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


    async def ainvoke(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if self.kind == "analyze":
            return await _analyze_handler(payload)
        elif self.kind == "report":
            return await _report_handler(payload)
        elif self.kind == "scope":
            return await _scope_handler(payload)
        elif self.kind == "scope_summary":
            return await _scope_summary_handler(payload)
        elif self.kind == "schedule":
            return await _schedule_handler(payload)
        elif self.kind == "schedule_timeline":
            return await _schedule_timeline_handler(payload)
        elif self.kind == "workflow_scope_then_schedule":
            return await _workflow_scope_then_schedule_handler(payload)
        else:
            raise ValueError(f"Unknown pipeline kind: {self.kind}")


# ===============================
#  분석 핸들러 1021
# ===============================
async def _analyze_handler(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyzer + optional Scope/Schedule handler.
    - payload keys: project_id, title, text, doc_type, mode/run_scope/save_items, methodology, calendar, sprint_length_weeks
    - behavior:
      - mode 'analyze' (default): save document, run analyzer, save action items, return action_items summary
      - mode 'scope': run ScopeAgent/ScheduleAgent only, do NOT save action items
      - mode 'both': run scope AND save action items
    """
    # ------------------------
    # Helper functions
    # ------------------------
    def _utcnow():
        return datetime.utcnow()

    def _parse_date_safe(val: Any) -> Optional[date]:
        if val is None:
            return None
        if isinstance(val, date):
            return val
        s = str(val).strip()
        if not s:
            return None
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y%m%d", "%Y-%m-%dT%H:%M:%S"):
            try:
                return datetime.strptime(s, fmt).date()
            except Exception:
                pass
        try:
            return datetime.fromisoformat(s).date()
        except Exception:
            return None

    # ------------------------
    # DB 세션 획득 (프로젝트의 방식에 맞춰 수정 가능)
    # ------------------------
    try:
        db = next(get_db())  # 기존 프로젝트에서 get_db() 패턴을 사용하면 이 라인으로
    except Exception:
        # fallback: SessionLocal if available
        try:
            db = SessionLocal()
        except Exception:
            raise RuntimeError("Could not obtain DB session. Adjust _analyze_handler to your project's DB session method.")

    # ------------------------
    # 파라미터 체크 및 초기화
    # ------------------------
    try:
        project_id = payload.get("project_id")
        if project_id is None:
            raise ValueError("project_id is required")
        project_id = int(project_id)

        title = payload.get("title") or "PM 분석 문서"
        text = payload.get("text") or ""
        if not isinstance(text, str) or not text.strip():
            raise ValueError("text is empty")

        doc_type = (payload.get("doc_type") or "meeting").strip().lower()

        # mode parsing
        mode = (payload.get("mode") or "").lower()
        if not mode:
            mode = "scope" if payload.get("run_scope") else "analyze"
        save_items_flag = bool(payload.get("save_items", False))
        if mode == "both":
            run_scope = True
            save_items = True
        else:
            run_scope = (mode == "scope")
            save_items = (mode == "analyze") or save_items_flag

        # ------------------------
        # 1) 문서 저장 (항상)
        # ------------------------
        doc = pm_models.PM_Document(
            project_id=project_id,
            title=title,
            content=text,
            doc_type=doc_type,
            created_at=_utcnow(),
            uploaded_at=_utcnow(),
        )
        db.add(doc)
        db.flush()  # doc.id 확보
        meeting_id = doc.id  # 기본적으로 문서 id를 meeting_id로 사용

        # ------------------------
        # 2) Analyzer 실행 (회의록 유형만 수행)
        # ------------------------
        raw_items: List[Dict[str, Any]] = []
        if doc_type == "meeting":
            # 공용 analyzer 호출 (기존 util 함수 사용)
            raw_items = await _run_analyzer_with_timeout(text, project_id)
            if raw_items is None:
                raw_items = []

        # ------------------------
        # 3) Scope & Schedule (옵션)
        # ------------------------
        scope_out = None
        sched_out = None
        if run_scope:
            # ScopeAgent 사용 (기존 방식 유지)
            sa = ScopeAgent()
            # 여기서는 문서 텍스트로 간단 인제스트; 실제 구현에 맞게 변경 가능
            sa.ingest([text], chunk=payload.get("chunk_size", 500), overlap=payload.get("overlap", 100))
            items_for_scope = sa.extract_items()
            wbs = sa.synthesize_wbs(items_for_scope, payload.get("methodology", "waterfall"))
            scope_out = sa.write_outputs(items_for_scope, wbs)

            # Schedule
            sch = ScheduleAgent()
            est = sch.estimate(scope_out.get("wbs_json") if isinstance(scope_out, dict) else scope_out, payload.get("methodology", "waterfall"))
            rows, meta = sch.build_dag_and_schedule(est, payload.get("calendar", {}), payload.get("sprint_length_weeks"))
            sched_out = sch.write_outputs(rows, meta)

        # ------------------------
        # 4) Action Item 저장 (Analyzer 결과 기반) — scope 모드일 때는 저장하지 않음
        # ------------------------
        saved = 0
        errors: List[Dict[str, Any]] = []
        if save_items and raw_items:
            for idx, raw in enumerate(raw_items, start=1):
                try:
                    item = raw if isinstance(raw, dict) else dict(raw)

                    task = item.get("task") or item.get("title") or item.get("summary") or item.get("description") or ""
                    assignee = item.get("assignee") or item.get("owner") or None
                    priority = item.get("priority") or item.get("prio") or "Medium"
                    status = item.get("status") or "Open"
                    due = _parse_date_safe(item.get("due") or item.get("due_date") or item.get("deadline"))
                    module = item.get("module")
                    phase = item.get("phase")
                    evidence_span = item.get("evidence_span") or item.get("evidence") or None
                    expected_effort = item.get("expected_effort") or item.get("effort")
                    expected_value = item.get("expected_value") or item.get("value")

                    ai = pm_models.PM_ActionItem(
                        project_id=project_id,
                        document_id=doc.id,
                        meeting_id=meeting_id,
                        assignee=assignee,
                        task=task,
                        due_date=due,
                        priority=priority,
                        status=status,
                        module=module,
                        phase=phase,
                        evidence_span=str(evidence_span) if evidence_span is not None else None,
                        expected_effort=float(expected_effort) if expected_effort not in (None, "") else None,
                        expected_value=float(expected_value) if expected_value not in (None, "") else None,
                        created_at=_utcnow(),
                    )
                    db.add(ai)
                    saved += 1
                except Exception as e:
                    logger.exception("[ANALYZE] Failed to add action item idx=%s: %s", idx, e)
                    errors.append({"index": idx, "error": repr(e), "raw": str(raw)})

            # commit items
            try:
                db.commit()
            except Exception as e:
                db.rollback()
                logger.exception("[ANALYZE] commit failed when saving action items: %s", e)
                raise RuntimeError(f"commit failed: {e}")
        else:
            # action item 저장 안할 경우 문서만 커밋
            try:
                db.commit()
            except Exception as e:
                db.rollback()
                logger.exception("[ANALYZE] commit failed for doc only: %s", e)
                raise RuntimeError(f"commit failed: {e}")

        # ------------------------
        # 5) Action Item 요약 생성 (UI 포맷)
        # ------------------------
        action_summary = {
            "open_total": 0,
            "open_preview": [],
            "overdue": [],
            "upcoming_7d": [],
            "status_counts": {},
            "priority_counts": {},
        }

        try:
            # 프로젝트 전체 아이템을 기준으로 집계 (필요시 문서별로 제한 가능)
            items_q = db.query(pm_models.PM_ActionItem).filter(pm_models.PM_ActionItem.project_id == project_id)
            all_items = items_q.all()
            open_items = [i for i in all_items if (getattr(i, "status", None) or "Open") == "Open"]

            today = date.today()
            action_summary["open_total"] = len(open_items)

            # preview (최대 5개)
            preview = []
            for i in open_items[:5]:
                preview.append({
                    "id": getattr(i, "id", None),
                    "task": getattr(i, "task", None),
                    "assignee": getattr(i, "assignee", None),
                    "due": (getattr(i, "due_date", None).isoformat() if getattr(i, "due_date", None) else None),
                    "priority": getattr(i, "priority", None),
                    "status": getattr(i, "status", None),
                })
            action_summary["open_preview"] = preview

            overdue = []
            upcoming = []
            for i in open_items:
                d = getattr(i, "due_date", None)
                pd = None
                if d:
                    if isinstance(d, datetime):
                        pd = d.date()
                    elif isinstance(d, date):
                        pd = d
                    else:
                        pd = _parse_date_safe(str(d))
                if pd:
                    days = (pd - today).days
                    if days < 0:
                        overdue.append({
                            "id": getattr(i, "id", None),
                            "task": getattr(i, "task", None),
                            "assignee": getattr(i, "assignee", None),
                            "due": pd.isoformat(),
                        })
                    elif 0 <= days <= 7:
                        upcoming.append({
                            "id": getattr(i, "id", None),
                            "task": getattr(i, "task", None),
                            "assignee": getattr(i, "assignee", None),
                            "due": pd.isoformat(),
                        })
            action_summary["overdue"] = overdue
            action_summary["upcoming_7d"] = upcoming

            status_counts = {}
            priority_counts = {}
            for i in all_items:
                st = getattr(i, "status", None) or "Unknown"
                pr = getattr(i, "priority", None) or "None"
                status_counts[st] = status_counts.get(st, 0) + 1
                priority_counts[pr] = priority_counts.get(pr, 0) + 1
            action_summary["status_counts"] = status_counts
            action_summary["priority_counts"] = priority_counts

        except Exception as e:
            logger.exception("[ANALYZE] Failed to build action summary: %s", e)
            # 실패할 경우 빈 구조 유지

        # ------------------------
        # 6) 결과 조립
        # ------------------------
        result: Dict[str, Any] = {
            "ok": True,
            "project_id": project_id,
            "document_id": doc.id,
            "meeting_id": meeting_id,
            "doc_type": doc_type,
            "saved_action_items": saved,
            "analyzer_items_count": len(raw_items or []),
            "action_items": action_summary,
        }
        if scope_out is not None:
            result["scope"] = scope_out
        if sched_out is not None:
            result["schedule"] = sched_out
        if errors:
            result["errors"] = errors

        logger.info("[ANALYZE] finished project_id=%s doc_id=%s saved=%s items=%s", project_id, doc.id, saved, len(raw_items or []))
        return result

    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
        logger.exception("[ANALYZE] top-level failure: %s", e)
        raise RuntimeError(f"analyze failed: {e}")
    finally:
        try:
            db.close()
        except Exception:
            pass


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