# server/workflow/pm_graph.py
from __future__ import annotations
import asyncio
import re
from datetime import datetime, date
from typing import Any, Dict, List, Optional, Union, TYPE_CHECKING
import logging
import traceback
from pathlib import Path

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

# ============================================================
#  Global Config
# ============================================================
logger = logging.getLogger("pm.graph")

DATA_DIR = Path("data")

# Flags
_SCHEDULE_AVAILABLE = True
_SCOPE_AVAILABLE = True

# DB / 모델 import
try:
    from server.db.database import SessionLocal, get_db  # ✅ get_db 추가
    from server.db import pm_models
    _DB_AVAILABLE = True
except Exception as e:
    logger.warning("[DB] import failed: %s", e)
    SessionLocal = None
    get_db = None  # ✅ get_db None 처리
    pm_models = None
    _DB_AVAILABLE = False

# Analyzer
if TYPE_CHECKING:
    from server.workflow.agents.pm_analyzer import PM_AnalyzerAgent

try:
    from server.workflow.agents.pm_analyzer import PM_AnalyzerAgent
    ANALYZER_AVAILABLE = True
    _ANALYZER_INSTANCE: Optional["PM_AnalyzerAgent"] = None
except Exception as e:
    logger.warning("[ANALYZER] import failed: %s", e)
    PM_AnalyzerAgent = None
    ANALYZER_AVAILABLE = False
    _ANALYZER_INSTANCE = None

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
    logger.error(traceback.format_exc())
    ScopeAgent = None
    _SCOPE_AVAILABLE = False

# Schedule Agent import
try:
    from server.workflow.agents.schedule_agent.pipeline import ScheduleAgent
    _SCHEDULE_AVAILABLE = True
except Exception as e:
    logger.warning("[SCHEDULE_AGENT] import failed: %s", e)
    logger.error(traceback.format_exc())
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

# ✅ 날짜 파싱 유틸 (전역으로 이동)
def _parse_date_safe(val: Any) -> Optional[date]:
    """다양한 날짜 형식을 안전하게 파싱"""
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

# ✅ 숫자 변환 유틸 (전역으로 이동)
def _safe_float(val, logger_inst=None) -> Optional[float]:
    """
    숫자로 변환 가능한 경우 float를 반환하고, 아니면 None을 반환.
    logger가 주어지면 파싱 실패시 debug로 기록.
    """
    if val is None or val == "":
        return None
    # 이미 숫자형이면 바로 변환
    if isinstance(val, (int, float)):
        try:
            return float(val)
        except Exception:
            return None
    s = str(val).strip()
    if s == "":
        return None
    # 직접 float 변환 시도
    try:
        return float(s)
    except Exception:
        # 값이 '10 days' 같은 형태이면 숫자만 추출 시도
        m = re.search(r"[-+]?\d+(\.\d+)?", s)
        if m:
            try:
                return float(m.group(0))
            except Exception:
                pass
        if logger_inst is not None:
            logger_inst.debug("safe_float: could not parse numeric from %r", val)
        return None


# ===============================
#  Analyzer 실행 가드
# ===============================
async def _run_analyzer_with_timeout(text: str, project_id: int) -> List[Dict[str, Any]]:
    """
    PM_AnalyzerAgent.analyze_minutes()를 timeout-safe로 감싸는 함수.
    """
    if not (ANALYZER_AVAILABLE and PM_AnalyzerAgent is not None):
        logger.info("[ANALYZER] PM_AnalyzerAgent not available; skip")
        return []

    global _ANALYZER_INSTANCE
    if _ANALYZER_INSTANCE is None:
        try:
            _ANALYZER_INSTANCE = PM_AnalyzerAgent()
            logger.debug("[ANALYZER] PM_AnalyzerAgent instantiated")
        except Exception as e:
            logger.exception("[ANALYZER] failed to instantiate PM_AnalyzerAgent: %s", e)
            _ANALYZER_INSTANCE = None
            return []

    def _call_agent():
        try:
            return _ANALYZER_INSTANCE.analyze_minutes(text, project_meta={"project_id": project_id})
        except Exception as e:
            logger.exception("[ANALYZER] agent analyze_minutes exception: %s", e)
            return []

    try:
        raw = await asyncio.wait_for(asyncio.to_thread(_call_agent), timeout=ANALYZE_TIMEOUT_SEC)
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
#  분석 핸들러
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
    
    # ✅ DB 세션 획득 (get_db 사용)
    db = None
    try:
        if get_db is not None:
            db = next(get_db())
        elif SessionLocal is not None:
            db = SessionLocal()
        else:
            raise RuntimeError("Could not obtain DB session. DB module not available.")
    except Exception as e:
        logger.exception("[ANALYZE] Failed to get DB session: %s", e)
        raise RuntimeError(f"Could not obtain DB session: {e}")

    try:
        # ------------------------
        # 파라미터 체크 및 초기화
        # ------------------------
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

        logger.debug("[ANALYZE] project_id=%s mode=%s run_scope=%s save_items=%s doc_type=%s", 
                     project_id, mode, run_scope, save_items, doc_type)

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
        meeting_id = doc.id

        # ------------------------
        # 2) Analyzer 실행 (회의록 유형만 수행)
        # ------------------------
        raw_items: List[Dict[str, Any]] = []
        if doc_type == "meeting":
            raw_items = await _run_analyzer_with_timeout(text, project_id)
            if raw_items is None:
                raw_items = []
        logger.debug("[ANALYZE] analyzer returned %d raw_items", len(raw_items) if raw_items is not None else 0)

        # ------------------------
        # 3) Scope & Schedule (옵션)
        # ------------------------
        scope_out = None
        sched_out = None
        if run_scope:
            try:
                # ScopeAgent 사용
                if _SCOPE_AVAILABLE and ScopeAgent is not None:
                    sa = ScopeAgent(data_dir=str(DATA_DIR))
                    scope_payload = {
                        "project_name": f"Project-{project_id}",
                        "text": text,
                        "methodology": payload.get("methodology", "waterfall"),
                        "options": {
                            "chunk_size": payload.get("chunk_size", 500),
                            "overlap": payload.get("overlap", 100)
                        }
                    }
                    scope_out = await sa.pipeline(scope_payload)
                    logger.info("[ANALYZE] Scope completed")
                else:
                    logger.warning("[ANALYZE] ScopeAgent not available")

                # Schedule
                if _SCHEDULE_AVAILABLE and ScheduleAgent is not None and scope_out:
                    sch = ScheduleAgent(data_dir=str(DATA_DIR))
                    wbs_json = scope_out.get("wbs_json") or scope_out.get("wbs_json_path")
                    if wbs_json:
                        sched_payload = {
                            "project_id": f"Project-{project_id}",
                            "wbs_json": wbs_json,
                            "methodology": payload.get("methodology", "waterfall"),
                            "calendar": payload.get("calendar", {}),
                            "sprint_length_weeks": payload.get("sprint_length_weeks", 2)
                        }
                        sched_out = await sch.pipeline(sched_payload)
                        logger.info("[ANALYZE] Schedule completed")
                else:
                    logger.warning("[ANALYZE] ScheduleAgent not available or no WBS")
            
            except Exception as e:
                logger.exception("[ANALYZE] Scope/Schedule failed: %s", e)

        # ------------------------
        # 4) Action Item 저장
        # ------------------------
        saved = 0
        errors: List[Dict[str, Any]] = []
        if save_items and raw_items:
            for idx, raw in enumerate(raw_items, start=1):
                try:
                    item = raw if isinstance(raw, dict) else dict(raw)

                    task = item.get("task") or item.get("title") or item.get("summary") or item.get("description") or ""
                    if not task.strip():
                        continue
                        
                    assignee = item.get("assignee") or item.get("owner") or None
                    priority = item.get("priority") or item.get("prio") or "Medium"
                    status = item.get("status") or "Open"
                    due = _parse_date_safe(item.get("due") or item.get("due_date") or item.get("deadline"))
                    module = item.get("module")
                    phase = item.get("phase")
                    evidence_span = item.get("evidence_span") or item.get("evidence") or None
                    expected_effort = _safe_float(item.get("expected_effort") or item.get("effort"), logger)
                    expected_value = _safe_float(item.get("expected_value") or item.get("value"), logger)

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
                        expected_effort=expected_effort,
                        expected_value=expected_value,
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
            if not save_items:
                logger.info("[ANALYZE] save_items is False; skipping action item persistence")
            else:
                logger.info("[ANALYZE] no raw_items to save")
            try:
                db.commit()
            except Exception as e:
                db.rollback()
                logger.exception("[ANALYZE] commit failed for doc only: %s", e)
                raise RuntimeError(f"commit failed: {e}")

        # ------------------------
        # 5) Action Item 요약 생성
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
    if not _SCOPE_AVAILABLE or ScopeAgent is None:
        raise RuntimeError("ScopeAgent not available. Check server/workflow/agents/scope_agent/pipeline.py")

    agent = ScopeAgent(data_dir=str(DATA_DIR))
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
#  Schedule 핸들러 # 1114
# ===============================
async def _schedule_handler(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not _SCHEDULE_AVAILABLE or ScheduleAgent is None:
        logger.warning("[SCHEDULE] ScheduleAgent not available; returning empty schedule")
        return {
            "warn": "ScheduleAgent not available; returning empty schedule",
            "timeline": [],
            "plan_csv": None,
            "gantt_json": None,
            "critical_path": []
        }

    logger.info("[SCHEDULE] ScheduleAgent pipeline 시작")
    agent = ScheduleAgent(data_dir=str(DATA_DIR))
    
    try:
        result = await agent.pipeline(payload)
        return result
    except Exception as e:
        logger.error("[SCHEDULE_HANDLER] Schedule pipeline failed: %s", e)
        logger.error(traceback.format_exc())
        raise RuntimeError("Schedule analysis failed") from e


# ============================================================
#  Schedule Timeline
# ============================================================
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
    if "scope" in payload and "schedule" in payload:
        scope_payload = payload["scope"]
        schedule_payload = payload["schedule"]
        
        scope_result = await _scope_handler(scope_payload)
        
        wbs_json_path = scope_result.get("wbs_json_path") or scope_result.get("wbs_json")
        if wbs_json_path:
            schedule_payload["wbs_json"] = wbs_json_path
        
        schedule_result = await _schedule_handler(schedule_payload)
        
        return {
            "scope": scope_result,
            "schedule": schedule_result
        }
    else:
        scope_result = await _scope_handler(payload)
        wbs_json_path = scope_result.get("wbs_json_path") or scope_result.get("wbs_json")
        
        sched_payload = {
            "project_id": payload.get("project_id", "default"),
            "wbs_json": wbs_json_path
        }
        if wbs_json_path:
            sched_payload["wbs_json"] = wbs_json_path
        
        schedule_result = await _schedule_handler(sched_payload)
        
        return {
            "scope": scope_result,
            "schedule": schedule_result
        }


# ===============================
#  파이프라인 실행 진입점
# ===============================
# async def run_pipeline(kind: str, payload: Any) -> Dict[str, Any]:
#     """
#     진입부에서 payload 표준화:
#     - 대시보드/라우터에서 Pydantic 모델이 전달되든, dict이든, 항상 dict로 변환
#     - 여기서 변환해두면 하위 핸들러/에이전트에서 .get 사용해도 안전
#     """
#     norm = _to_dict(payload)
#     app = _App(kind)
#     return await app.ainvoke(norm)
class _App:
    def __init__(self, kind: str):
        self.kind = kind

    async def ainvoke(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if self.kind == "scope":
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


def create_debate_graph(kind: str = "scope"):
    return _App(kind)