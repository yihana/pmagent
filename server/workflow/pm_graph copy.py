# server/workflow/pm_graph.py
import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger("pm.graph")

# ===== (선택) Analyzer 연동: 없으면 자동 폴백 =====
try:
    from server.workflow.agents import analyzer  # optional
    _ANALYZER_AVAILABLE = True
except Exception as e:
    logger.warning("[ANALYZER] import failed: %s", e)
    analyzer = None
    _ANALYZER_AVAILABLE = False

# ===== (선택) DB 연동: 없으면 읽기/쓰기 건너뜀 =====
try:
    from server.db.database import SessionLocal  # optional
    from server.db import pm_models             # optional
    _DB_AVAILABLE = True
except Exception as e:
    logger.warning("[DB] import failed: %s", e)
    SessionLocal = None
    pm_models = None
    _DB_AVAILABLE = False

# ===== (선택) Scope/Schedule Agent 연동 =====
try:
    from server.workflow.agents.scope_agent.pipeline import ScopeAgent  # optional
    _SCOPE_AVAILABLE = True
except Exception as e:
    logger.warning("[SCOPE_AGENT] import failed: %s", e)
    ScopeAgent = None
    _SCOPE_AVAILABLE = False

try:
    from server.workflow.agents.schedule_agent.pipeline import ScheduleAgent  # optional
    _SCHEDULE_AVAILABLE = True
except Exception as e:
    logger.warning("[SCHEDULE_AGENT] import failed: %s", e)
    ScheduleAgent = None
    _SCHEDULE_AVAILABLE = False


# ================= 공용 유틸 =================
def _resolve_data_dir() -> Path:
    here = Path(__file__).resolve()
    for p in here.parents:
        if (p / "data").exists():
            return p / "data"
    return here.parents[1] / "data"

DATA_DIR = _resolve_data_dir()

def _to_dict(obj: Any) -> Dict[str, Any]:
    """Pydantic(BaseModel) 등 어떤 형태든 안전하게 dict로 표준화."""
    if isinstance(obj, dict):
        return obj
    md = getattr(obj, "model_dump", None)
    if callable(md):
        try:
            return md()
        except Exception:
            pass
    dct = getattr(obj, "dict", None)
    if callable(dct):
        try:
            return dct()
        except Exception:
            pass
    try:
        return dict(obj)
    except Exception:
        return {"value": obj}

def _read_text_file_maybe(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        try:
            return path.read_text(encoding="cp949")
        except Exception:
            return ""

def _load_minutes_by_filename(filename: str) -> str:
    # minutes → RFP → 루트 순으로 텍스트 로드
    candidates = [
        DATA_DIR / "inputs" / "minutes" / filename,
        DATA_DIR / "inputs" / "RFP" / filename,
        DATA_DIR / filename,
    ]
    for p in candidates:
        if p.exists() and p.is_file():
            if p.suffix.lower() in (".txt", ".md"):
                return _read_text_file_maybe(p)
            elif p.suffix.lower() == ".pdf":
                return f"[WARN] PDF ingestion not implemented: {p.name}"
            else:
                return f"[WARN] Unsupported file type: {p.name}"
    return f"[WARN] file not found: {filename}"

def _basic_action_item_extractor(text: str) -> List[Dict[str, Any]]:
    """간단 불릿/숫자/키워드 기반 액션 추출기 (analyzer 부재 시 사용)"""
    items: List[Dict[str, Any]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith(("-", "*")) or line[:1].isdigit() or "TODO" in line.upper() or "ACTION" in line.upper():
            items.append({"text": line, "assignee": None, "due": None})
    if not items:
        # 아무것도 못 찾으면 상위 3줄을 액션처럼 반환
        for i, raw in enumerate([l for l in text.splitlines() if l.strip()], 1):
            items.append({"text": raw.strip(), "assignee": None, "due": None})
            if i >= 3:
                break
    return items


# ================= Handlers =================
async def _analyze_handler(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    입력: {project_id, title?, text? | filename?}
    출력: {"project_id", "title", "action_items":[...]}
    - analyzer가 있으면 analyzer로, 없으면 내부 추출기로 동작
    - filename만 있어도 파일에서 텍스트 읽어 분석
    """
    filename = payload.get("filename")
    text = payload.get("text") or ""
    if filename and not text:
        text = _load_minutes_by_filename(filename)

    project_id = payload.get("project_id")
    title = payload.get("title") or (filename or "Untitled")

    result: Dict[str, Any] = {
        "project_id": project_id,
        "title": title,
        "action_items": [],
    }

    # analyzer 모듈이 있으면 우선 사용
    if _ANALYZER_AVAILABLE and analyzer is not None:
        try:
            items = await asyncio.to_thread(analyzer.analyze_minutes, text)  # type: ignore
            result["action_items"] = items or []
            # (선택) DB 저장
            if _DB_AVAILABLE:
                try:
                    db = SessionLocal()
                    try:
                        if hasattr(pm_models, "PM_Document"):
                            doc = pm_models.PM_Document(project_id=project_id, title=title, content=text)
                            db.add(doc); db.flush()
                            if hasattr(pm_models, "PM_Action"):
                                for it in items or []:
                                    db.add(pm_models.PM_Action(
                                        project_id=project_id, document_id=doc.id,
                                        text=it.get("text"), assignee=it.get("assignee"), due=it.get("due")
                                    ))
                            db.commit()
                    finally:
                        db.close()
                except Exception as e:
                    logger.warning("[DB] analyze save skipped: %s", e)
            return result
        except Exception as e:
            logger.exception("[ANALYZE] analyzer failed: %s", e)

    # 폴백: 내부 간단 추출기
    result["action_items"] = _basic_action_item_extractor(text)

    # (선택) DB 저장 시도
    if _DB_AVAILABLE:
        try:
            db = SessionLocal()
            try:
                if hasattr(pm_models, "PM_Document"):
                    doc = pm_models.PM_Document(project_id=project_id, title=title, content=text)
                    db.add(doc); db.flush()
                    if hasattr(pm_models, "PM_Action"):
                        for it in result["action_items"]:
                            db.add(pm_models.PM_Action(
                                project_id=project_id, document_id=doc.id,
                                text=it.get("text"), assignee=it.get("assignee"), due=it.get("due")
                            ))
                    db.commit()
            finally:
                db.close()
        except Exception as e:
            logger.warning("[DB] analyze fallback save skipped: %s", e)

    return result


async def _report_handler(payload: Dict[str, Any]) -> Dict[str, Any]:
    """주간 리포트: DB가 있으면 간단 집계, 없으면 스텁"""
    project_id = payload.get("project_id")
    fast = bool(payload.get("fast"))

    if _DB_AVAILABLE:
        try:
            db = SessionLocal()
            try:
                summary = {"project_id": project_id, "fast": fast, "highlights": [], "counts": {}}
                if hasattr(pm_models, "PM_Document"):
                    summary["counts"]["documents"] = db.query(pm_models.PM_Document)\
                                                       .filter(pm_models.PM_Document.project_id == project_id)\
                                                       .count()
                if hasattr(pm_models, "PM_Action"):
                    summary["counts"]["actions"] = db.query(pm_models.PM_Action)\
                                                     .filter(pm_models.PM_Action.project_id == project_id)\
                                                     .count()
                summary["summary"] = "Auto-generated weekly report"
                return summary
            finally:
                db.close()
        except Exception as e:
            logger.warning("[DB] report skipped: %s", e)

    # DB 없을 때 스텁
    return {"project_id": project_id, "fast": fast, "summary": "Auto-generated weekly report", "highlights": []}


async def _scope_handler(payload: Dict[str, Any]) -> Dict[str, Any]:
    """ScopeAgent 파이프라인 호출 (미존재 시 RuntimeError)"""
    if not _SCOPE_AVAILABLE or ScopeAgent is None:
        raise RuntimeError("ScopeAgent not available. Check server/workflow/agents/scope_agent/pipeline.py")
    agent = ScopeAgent(data_dir=str(DATA_DIR))
    return await agent.pipeline(payload)


async def _scope_summary_handler(payload: Dict[str, Any]) -> Dict[str, Any]:
    project_id = payload.get("project_id")
    out_dir = Path(DATA_DIR) / "outputs" / "scope" / str(project_id)
    info = {"project_id": project_id, "exists": out_dir.exists(), "files": []}
    if out_dir.exists():
        for p in sorted(out_dir.glob("*")):
            info["files"].append({"name": p.name, "size": p.stat().st_size})
    return info


async def _schedule_handler(payload: Dict[str, Any]) -> Dict[str, Any]:
    """ScheduleAgent 파이프라인 (미존재 시 경고와 함께 빈 결과 반환)"""
    if not _SCHEDULE_AVAILABLE or ScheduleAgent is None:
        return {"warn": "ScheduleAgent not available; returning empty schedule", "timeline": []}
    agent = ScheduleAgent(data_dir=str(DATA_DIR))
    return await agent.pipeline(payload)


async def _schedule_timeline_handler(payload: Dict[str, Any]) -> Dict[str, Any]:
    project_id = payload.get("project_id")
    out_dir = Path(DATA_DIR) / "outputs" / "schedule" / str(project_id)
    f = out_dir / "timeline.json"
    if f.exists():
        return {"project_id": project_id, "timeline_path": str(f), "size": f.stat().st_size}
    return {"project_id": project_id, "timeline_path": None}


async def _workflow_scope_then_schedule_handler(payload: Dict[str, Any]) -> Dict[str, Any]:
    """scope → schedule 연계 실행"""
    scope_result = await _scope_handler(payload)
    wbs_json_path = scope_result.get("wbs_json_path")
    sched_payload = {"project_id": payload.get("project_id"), "wbs_json": wbs_json_path}
    sched_result = await _schedule_handler(sched_payload)
    return {"scope": scope_result, "schedule": sched_result}


# ================= App / Pipeline 엔트리 =================
@dataclass
class _App:
    kind: str
    def __init__(self, kind: str):
        # ✅ 과거 init 오타 → __init__ 확정
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

async def run_pipeline(kind: str, payload: Any) -> Dict[str, Any]:
    """
    ✅ 진입부에서 payload 표준화:
    - 대시보드/라우터에서 Pydantic 모델이 전달되든, dict이든, 항상 dict로 변환
    - 여기서 변환해두면 하위 핸들러/에이전트에서 .get 사용해도 안전
    """
    norm = _to_dict(payload)
    app = _App(kind)
    return await app.ainvoke(norm)
