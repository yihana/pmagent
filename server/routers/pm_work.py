from __future__ import annotations
import os
import json
import shutil
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Request, HTTPException, status, Depends, Query, UploadFile, File
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
import logging

from server.workflow.pm_graph import run_pipeline  # pipeline entry
from server.utils.logger import get_logger

# DB crud helpers (used in modified endpoints)
from server.db.database import get_db
from server.db import pm_crud, pm_models

logger = get_logger("router.pm_work") if hasattr(__import__("server.utils.logger", fromlist=["get_logger"]), "get_logger") else __import__("logging").getLogger("router.pm_work")

router = APIRouter(prefix="/api/v1", tags=["pm"])

# Ensure upload directory exists (from original first source)
UPLOAD_DIR = Path("data/inputs/RFP")
try:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    # best-effort; log and continue
    logger.debug("Could not create upload directory", exc_info=True)


# ----------------------------
# Local Pydantic request/response models
# ----------------------------
class DocumentRef(BaseModel):
    path: str
    type: Optional[str] = None
    title: Optional[str] = None

class ScopeRequest(BaseModel):
    project_id: Optional[str] = None
    project_name: Optional[str] = None
    documents: Optional[List[Dict[str, Any]]] = None
    text: Optional[str] = None         # 새/권장 키
    rfp_text: Optional[str] = None     # 기존 프론트가 보낼 수 있는 키(호환)
    options: Optional[Dict[str, Any]] = None
    methodology: Optional[str] = "waterfall"

    def get_text(self) -> Optional[str]:
        if self.text and isinstance(self.text, str) and self.text.strip():
            return self.text.strip()
        if self.rfp_text and isinstance(self.rfp_text, str) and self.rfp_text.strip():
            return self.rfp_text.strip()
        return None

class ScheduleRequest(BaseModel):
    project_id: Optional[int] = None
    methodology: Optional[str] = "waterfall"
    wbs_json: Optional[str] = None  # could be JSON string or path
    calendar: Optional[Dict[str, Any]] = None
    sprint_length_weeks: Optional[int] = 2
    estimation_mode: Optional[str] = "heuristic"
    change_requests: Optional[List[Dict[str, Any]]] = None
    sprint_backlogs: Optional[List[Dict[str, Any]]] = None
    options: Optional[Dict[str, Any]] = None

class AnalyzeRequest(BaseModel):
    project_id: Optional[int] = Field(default=1001)
    title: Optional[str] = None
    text: Optional[str] = None
    doc_type: Optional[str] = "meeting"
    mode: Optional[str] = None
    run_scope: Optional[bool] = False
    save_items: Optional[bool] = True
    methodology: Optional[str] = "waterfall"
    options: Optional[Dict[str, Any]] = None

class WorkflowRequest(BaseModel):
    scope: Optional[Dict[str, Any]] = None
    schedule: Optional[Dict[str, Any]] = None
    project_id: Optional[int] = None
    documents: Optional[List[DocumentRef]] = None
    rfp_text: Optional[str] = None
    wbs_json: Optional[str] = None

# Response models (from first/original source)
class AnalyzeResponse(BaseModel):
    status: str = "ok"
    data: Dict[str, Any] | list | None = None
    message: Optional[str] = None

class ReportResponse(BaseModel):
    status: str = "ok"
    data: Dict[str, Any] | list | None = None
    message: Optional[str] = None


# ----------------------------
# Helpers
# ----------------------------
def _to_dict(obj: Any) -> Dict[str, Any]:
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    md = getattr(obj, "model_dump", None)
    if callable(md):
        try:
            return md()
        except Exception:
            pass
    d = getattr(obj, "dict", None)
    if callable(d):
        try:
            return d()
        except Exception:
            pass
    out = {}
    for k in dir(obj):
        if k.startswith("_"):
            continue
        try:
            v = getattr(obj, k)
            if not callable(v):
                out[k] = v
        except Exception:
            continue
    return out

def _read_texts_from_documents(doc_refs: Optional[List[DocumentRef]]) -> str:
    if not doc_refs:
        return ""
    pieces = []
    for d in doc_refs:
        path = d.path
        p = Path(path)
        if not p.is_absolute():
            repo_root = Path(__file__).resolve().parents[3]
            candidate = repo_root / "data" / "inputs" / "RFP" / path
            if candidate.exists():
                p = candidate
            else:
                candidate2 = Path.cwd() / path
                if candidate2.exists():
                    p = candidate2
        if not p.exists():
            logger.warning("[pm_work] referenced document not found: %s", path)
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
            pieces.append(f"--- FILE: {p.name} ---\n{text}")
        except Exception as e:
            logger.exception("[pm_work] failed to read document %s: %s", p, e)
            continue
    return "\n\n".join(pieces)

def _normalize_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    if isinstance(payload, dict):
        return payload
    md = getattr(payload, "model_dump", None)
    if callable(md):
        return md()
    dct = getattr(payload, "dict", None)
    if callable(dct):
        return dct()
    return dict(payload)


# ----------------------------
# Endpoints
# ----------------------------
@router.post("/pm/upload/rfp")
async def upload_rfp(file: UploadFile = File(...)):
    """
    RFP PDF 파일 업로드
    - 클라이언트에서 파일을 업로드받아 서버 경로(data/inputs/RFP)에 저장
    - 저장된 파일의 서버 경로를 반환하여 Scope/Schedule Agent에서 사용
    """
    try:
        # 파일 확장자 검증
        if not file.filename.lower().endswith('.pdf'):
            raise HTTPException(status_code=400, detail="PDF 파일만 업로드 가능합니다.")

        # 파일명 안전하게 처리
        filename = file.filename.replace(" ", "_")
        file_path = UPLOAD_DIR / filename

        # 파일 저장
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # 상대경로 반환
        relative_path = f"data/inputs/RFP/{filename}"

        logger.info(f"[UPLOAD] File saved: {relative_path}")

        return {
            "status": "ok",
            "filename": filename,
            "path": relative_path,
            "size": file_path.stat().st_size,
            "message": f"파일이 업로드되었습니다: {relative_path}"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"[UPLOAD] Failed: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"파일 업로드 실패: {str(e)}")


@router.post("/pm/scope/analyze")
async def scope_analyze(request: ScopeRequest, db: Session = Depends(get_db)):
    try:
        project_name = request.project_name or "default"
        methodology = request.methodology or "waterfall"

        logger.info(f"[Scope Agent] Starting analysis for project: {project_name}")

        payload = _to_dict(request)
        text_val = request.get_text() if hasattr(request, "get_text") else None
        if not payload.get("text") and text_val:
            payload["text"] = text_val
        if not payload.get("text") and payload.get("documents"):
            try:
                docs = payload.get("documents")
                doc_objs = []
                for d in docs:
                    if isinstance(d, dict):
                        doc_objs.append(DocumentRef(**d))
                    elif isinstance(d, DocumentRef):
                        doc_objs.append(d)
                text_from_files = _read_texts_from_documents(doc_objs)
                if text_from_files and not payload.get("text"):
                    payload["text"] = text_from_files
            except Exception:
                logger.debug("Failed to read document files for payload text", exc_info=True)

        result = await run_pipeline(kind="scope", payload=payload)

        try:
            project = pm_crud.get_or_create_project(
                db,
                project_id=hash(project_name) % 1000000,
                name=project_name
            )

            scope_record = pm_crud.save_scope_result(
                db,
                project_id=project.id,
                scope_json=result
            )

            pm_crud.log_event(
                db,
                event_type="scope_generated",
                message=f"Scope generated for project: {project_name}",
                details={
                    "project_id": project.id,
                    "methodology": methodology,
                }
            )

            logger.info(f"[Scope Agent] Results saved to DB (scope_id: {getattr(scope_record, 'id', 'unknown')})")

        except Exception as db_error:
            logger.error(f"[Scope Agent] DB save failed: {db_error}", exc_info=True)

        return JSONResponse(
            content={
                "status": "ok",
                "scope_statement_md": result.get("scope_md_path") or result.get("scope_statement_md"),
                "rtm_csv": result.get("rtm_csv_path") or result.get("rtm_csv"),
                "wbs_json": result.get("wbs_json_path") or result.get("wbs_json"),
                "data": result
            },
            status_code=200
        )
    except Exception as e:
        logger.exception(f"[Scope Agent] Error: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    

@router.post("/pm/schedule/analyze")
async def schedule_analyze(request: ScheduleRequest, db: Session = Depends(get_db)):
    try:
        project_id = request.project_id or "default"
        methodology = request.methodology or "waterfall"

        logger.info(f"[Schedule Agent] Starting analysis for project: {project_id}")

        payload = _to_dict(request)
        if payload.get("wbs_json"):
            wbs_candidate = payload["wbs_json"]
            try:
                p = Path(wbs_candidate)
                if not p.is_absolute():
                    repo_root = Path(__file__).resolve().parents[3]
                    candidate = repo_root / "data" / "inputs" / "RFP" / wbs_candidate
                    if candidate.exists():
                        p = candidate
                    else:
                        candidate2 = Path.cwd() / wbs_candidate
                        if candidate2.exists():
                            p = candidate2
                if p.exists():
                    try:
                        payload["wbs_json"] = json.loads(p.read_text(encoding="utf-8", errors="ignore"))
                    except Exception:
                        payload["wbs_json_path"] = str(p)
            except Exception:
                logger.debug("Failed to normalize wbs_json path/content", exc_info=True)

        result = await run_pipeline(kind="schedule", payload=payload)

        try:
            project = pm_crud.get_or_create_project(
                db,
                project_id=hash(str(project_id)) % 1000000,
                name=str(project_id)
            )

            schedule_record = pm_crud.save_schedule_result(
                db,
                project_id=project.id,
                schedule_json=result,
                methodology=methodology
            )

            pm_crud.log_event(
                db,
                event_type="schedule_generated",
                message=f"Schedule generated for project: {project_id}",
                details={
                    "project_id": project.id,
                    "methodology": methodology,
                }
            )

            logger.info(f"[Schedule Agent] Results saved to DB (schedule_id: {getattr(schedule_record, 'id', 'unknown')})")

        except Exception as db_error:
            logger.error(f"[Schedule Agent] DB save failed: {db_error}", exc_info=True)

        return JSONResponse(
            content={
                "status": "ok",
                "plan_csv": result.get("plan_csv"),
                "gantt_json": result.get("gantt_json"),
                "critical_path": result.get("critical_path"),
                "data": result
            },
            status_code=200
        )
    except Exception as e:
        logger.exception(f"[Schedule Agent] Error: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ----------------------------
# Graph analyzer & report endpoints (restored from first/original source)
# ----------------------------
@router.post("/pm/graph/analyze", response_model=AnalyzeResponse)
async def graph_analyze(payload: AnalyzeRequest, db: Session = Depends(get_db)):
    """
    Graph-based analyzer (original behavior):
    - Run run_pipeline(kind="analyze", payload=payload)
    - After saving, if action items were saved, fetch them from DB and include actual list in response
    """
    try:
        # Ensure we convert Pydantic model to dict consistently
        p = _to_dict(payload)
        result = await run_pipeline(kind="analyze", payload=p)

        project_id = result.get("project_id")
        saved_count = result.get("saved_action_items", 0)

        action_items_list = []
        if saved_count > 0 and project_id:
            try:
                document_id = result.get("document_id")
                if document_id is not None:
                    items = db.query(pm_models.PM_ActionItem).filter(pm_models.PM_ActionItem.document_id == document_id).all()
                    action_items_list = [
                        {
                            "id": item.id,
                            "task": item.task,
                            "assignee": item.assignee,
                            "due_date": str(item.due_date) if item.due_date else None,
                            "priority": item.priority,
                            "status": item.status,
                            "module": item.module,
                            "phase": item.phase
                        }
                        for item in items
                    ]
            except Exception as e:
                logger.warning(f"[Analyze] Failed to fetch action items: {e}")

        response_data = {
            "ok": result.get("ok", True),
            "project_id": project_id,
            "document_id": result.get("document_id"),
            "meeting_id": result.get("meeting_id"),
            "saved_action_items": saved_count,
            "action_items": action_items_list,
            "action_items_summary": result.get("action_items"),
            "title": p.get("title") or "Untitled",
            "doc_type": p.get("doc_type") or "meeting"
        }

        return AnalyzeResponse(
            status="ok",
            data=response_data,
            message=f"분석 완료: {saved_count}개 액션 아이템 저장됨"
        )
    except Exception as e:
        logger.exception(f"[Analyze] Error: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pm/graph/report", response_model=ReportResponse)
async def graph_report(project_id: int = Query(..., description="프로젝트 ID"), fast: Optional[bool] = Query(False, description="compat flag")):
    """
    Report endpoint (restored): forwards to run_pipeline(kind='report').
    Accepts optional query params; 'fast' is ignored but accepted for compatibility.
    """
    try:
        result = await run_pipeline(kind="report", payload={"project_id": project_id})
        return ReportResponse(status="ok", data=result)
    except Exception as e:
        logger.exception(f"[Report] Error: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------
# Workflow endpoint: scope -> schedule convenience wrapper (unchanged)
# ---------------------------------------------------------------------
@router.post("/pm/workflow/scope-then-schedule")
async def workflow_scope_then_schedule(request: WorkflowRequest):
    payload = _to_dict(request)
    if payload.get("scope") and payload.get("schedule"):
        try:
            from server.workflow.pm_graph import run_pipeline
        except Exception:
            run_pipeline = None

        if run_pipeline:
            try:
                result = await run_pipeline(kind="workflow_scope_then_schedule", payload=payload)
                return result
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"workflow pipeline failed: {e}")
        else:
            try:
                from server.workflow.agents.scope_agent.pipeline import ScopeAgent
                from server.workflow.agents.schedule_agent.pipeline import ScheduleAgent
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Required agents not available: {e}")

            scope_agent = ScopeAgent()
            schedule_agent = ScheduleAgent()

            scope_out = await scope_agent.pipeline(payload["scope"])
            sched_payload = payload["schedule"]
            if "wbs_json" not in sched_payload:
                sched_payload["wbs_json"] = scope_out.get("wbs_json") or scope_out.get("wbs_json_path")
            sched_out = await schedule_agent.pipeline(sched_payload)
            return {"scope": scope_out, "schedule": sched_out}
    else:
        raise HTTPException(status_code=400, detail="Both 'scope' and 'schedule' sections required in payload")


# Optional: simple health / info endpoints
@router.get("/pm/health")
async def health():
    return {"ok": True, "service": "pm_work_router"}


@router.get("/pm/routes")
async def routes_info():
    return {
        "routes": [
            "/pm/upload/rfp (POST)",
            "/pm/scope/analyze (POST)",
            "/pm/schedule/analyze (POST)",
            "/pm/graph/analyze (POST)",
            "/pm/graph/report (GET)",
            "/pm/workflow/scope-then-schedule (POST)"
        ]
    }