# server/routers/pm_work.py
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Body
from fastapi.responses import JSONResponse
from pathlib import Path
import shutil

from server.workflow.pm_graph import run_pipeline

# ✅ 대시보드와 1:1 매칭되는 절대 prefix
router = APIRouter(prefix="/api/v1/pm", tags=["pm"])

# ---- 파일 저장 위치 ----
DATA_DIR = Path("data")
UPLOAD_RFP_DIR = DATA_DIR / "inputs" / "RFP"
UPLOAD_MINUTES_DIR = DATA_DIR / "inputs" / "minutes"
for d in (UPLOAD_RFP_DIR, UPLOAD_MINUTES_DIR):
    d.mkdir(parents=True, exist_ok=True)

# ================= Upload =================
@router.post("/upload/rfp")
async def upload_rfp(file: UploadFile = File(...), project_id: Optional[int] = None):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="PDF only")
    out_path = UPLOAD_RFP_DIR / file.filename
    with out_path.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    return {"ok": True, "saved_as": str(out_path), "project_id": project_id}

@router.post("/upload/minutes")
async def upload_minutes(file: UploadFile = File(...), project_id: Optional[int] = None):
    if not any(file.filename.lower().endswith(ext) for ext in (".txt", ".md")):
        raise HTTPException(status_code=400, detail="TXT or MD only")
    out_path = UPLOAD_MINUTES_DIR / file.filename
    with out_path.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    return {"ok": True, "saved_as": str(out_path), "project_id": project_id}

# ================= Analyze =================
@router.post("/graph/analyze")
async def graph_analyze(payload: Dict[str, Any] = Body(default={})):
    """
    요청 예:
    {
      "project_id": 1001,
      "title": "주간회의",
      "text": "회의록 원문"    # 또는
      "filename": "meeting_1017.md"
    }
    """
    result = await run_pipeline(kind="analyze", payload=payload)
    return JSONResponse({"status": "ok", "data": result})

@router.get("/graph/report")
async def graph_report(project_id: int = Query(...), fast: bool = Query(False)):
    result = await run_pipeline(kind="report", payload={"project_id": project_id, "fast": fast})
    return JSONResponse({"status": "ok", "data": result})

# ================= Scope =================
@router.post("/scope/analyze")
async def scope_analyze(payload: Dict[str, Any] = Body(default={})):
    try:
        result = await run_pipeline(kind="scope", payload=payload)
        return JSONResponse({"status": "ok", "data": result})
    except RuntimeError as e:
        # ScopeAgent 미구현/임포트 실패 등은 503로 명확히
        raise HTTPException(status_code=503, detail=str(e)) from e

@router.get("/scope/summary")
async def scope_summary(project_id: int = Query(...)):
    result = await run_pipeline(kind="scope_summary", payload={"project_id": project_id})
    return JSONResponse({"status": "ok", "data": result})

# ================= Schedule =================
@router.post("/schedule/analyze")
async def schedule_analyze(payload: Dict[str, Any] = Body(default={})):
    result = await run_pipeline(kind="schedule", payload=payload)
    return JSONResponse({"status": "ok", "data": result})

@router.get("/schedule/timeline")
async def schedule_timeline(project_id: int = Query(...)):
    result = await run_pipeline(kind="schedule_timeline", payload={"project_id": project_id})
    return JSONResponse({"status": "ok", "data": result})

# ================= Workflow =================
@router.post("/workflow/scope-then-schedule")
async def workflow_scope_then_schedule(payload: Dict[str, Any] = Body(default={})):
    """
    { "project_id": 1001, "text": "...", "options": {"wbs_depth": 3} }
    를 받아 scope → schedule 순차 실행
    """
    result = await run_pipeline(kind="workflow_scope_then_schedule", payload=payload)
    return JSONResponse({"status": "ok", "data": result})
