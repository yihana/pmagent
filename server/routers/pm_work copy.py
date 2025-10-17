# server/routers/pm_work.py
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, Request, HTTPException, Query, UploadFile, File
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import traceback
import shutil
from pathlib import Path
from server.workflow.pm_graph import run_pipeline

router = APIRouter(prefix="/api/v1/pm", tags=["pm"])

# 업로드 디렉토리
DATA_DIR = Path("data")
UPLOAD_DIR = Path("data/inputs/RFP")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# ===== 공용 모델 =====
class AnalyzeRequest(BaseModel):
    project_id: int | str = Field(..., description="프로젝트 ID")
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

# ===== Scope 관련 모델 =====
class DocumentRef(BaseModel):
    path: str
    type: Optional[str] = "RFP"

class ScopeRequest(BaseModel):
    project_id: Optional[int | str] = Field(default=None, description="프로젝트 ID (선택)")
    project_name: Optional[str] = Field(default=None, description="프로젝트명 (선택)")
    methodology: Optional[str] = Field(default="waterfall")
    documents: List[DocumentRef] = Field(..., description="문서 목록 (서버 경로)")
    options: Optional[Dict[str, Any]] = Field(default=None, description="ingest 옵션 (chunk_size, overlap 등)")
    enable_rag: Optional[bool] = Field(default=True)

class ScopeResponse(BaseModel):
    status: str = "ok"
    scope_statement_md: Optional[str] = None
    rtm_csv: Optional[str] = None
    wbs_json: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    message: Optional[str] = None

# ===== Schedule 관련 모델 =====
class CalendarModel(BaseModel):
    start_date: str
    work_week: Optional[List[int]] = Field(default=[1,2,3,4,5])
    holidays: Optional[List[str]] = Field(default=[])

class ResourceModel(BaseModel):
    role: str
    capacity_pct: Optional[int] = 100

class ScheduleRequest(BaseModel):
    project_id: Optional[int | str] = Field(default=None)
    wbs_json: str = Field(..., description="서버내 WBS JSON 경로")
    calendar: CalendarModel
    resource_pool: Optional[List[ResourceModel]] = Field(default=[])
    sprint_length_weeks: Optional[int] = 2
    estimation_mode: Optional[str] = "llm"
    methodology: Optional[str] = "waterfall"

class ScheduleResponse(BaseModel):
    status: str = "ok"
    plan_csv: Optional[str] = None
    gantt_json: Optional[str] = None
    critical_path: Optional[list] = None
    data: Optional[Dict[str, Any]] = None
    message: Optional[str] = None

# ===== Workflow (Scope -> Schedule) 모델 =====
class WorkflowPayload(BaseModel):
    scope: ScopeRequest
    schedule: ScheduleRequest

class WorkflowResponse(BaseModel):
    status: str = "ok"
    scope: Optional[Dict[str, Any]] = None
    schedule: Optional[Dict[str, Any]] = None
    message: Optional[str] = None

# -----------------------
# 신규: 파일 업로드 엔드포인트
# -----------------------
@router.post("/upload/rfp")
async def upload_rfp(file: UploadFile = File(...), project_id: Optional[int] = None):
    """
    RFP PDF 파일 업로드
    - 클라이언트(Streamlit)에서 파일을 업로드받아 서버 경로에 저장
    - 저장된 파일의 서버 경로를 반환하여 Scope/Schedule Agent에서 사용
    """
    try:
        # 파일 확장자 검증
        if not file.filename.lower().endswith('.pdf'):
            raise HTTPException(status_code=400, detail="PDF 파일만 업로드 가능합니다.")
        
        # 파일 저장
        file_path = UPLOAD_DIR / file.filename
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        return {
            "status": "ok",
            "filename": file.filename,
            "path": str(file_path),
            "message": f"파일이 업로드되었습니다: {file_path}"
        }
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"파일 업로드 실패: {str(e)}")

# -----------------------
# 기존: 그래프 분석 / 리포트
# -----------------------
@router.post("/graph/analyze", response_model=AnalyzeResponse)
async def graph_analyze(payload: AnalyzeRequest):
    """
    기존 엔드포인트 유지: 그래프 기반 분석 호출
    run_pipeline(kind="analyze", payload=payload.model_dump())
    """
    try:
        result = await run_pipeline(kind="analyze", payload=payload.model_dump())
        return AnalyzeResponse(status="ok", data=result)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/graph/report", response_model=ReportResponse)
async def graph_report(project_id: int = Query(..., description="프로젝트 ID")):
    """
    기존 리포트 조회 엔드포인트
    """
    try:
        result = await run_pipeline(kind="report", payload={"project_id": project_id})
        return ReportResponse(status="ok", data=result)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# -----------------------
# 신규: Scope Agent (범위관리)
# -----------------------
@router.post("/scope/analyze", response_model=ScopeResponse)
async def scope_analyze(payload: ScopeRequest):
    try:
        result = await run_pipeline(kind="scope", payload=payload)
        return JSONResponse({"status": "ok", "data": result})
    except RuntimeError as e:
        # 모듈 미구현/임포트 실패는 503으로
        raise HTTPException(status_code=503, detail=str(e)) from e

@router.get("/scope/summary", response_model=ScopeResponse)
async def scope_summary(project_id: int = Query(...)):
    result = await run_pipeline(kind="scope_summary", payload={"project_id": project_id})
    return JSONResponse({"status": "ok", "data": result})

# -----------------------
# 신규: Schedule Agent (일정관리)
# -----------------------
@router.post("/schedule/analyze", response_model=ScheduleResponse)
async def schedule_analyze(payload: ScheduleRequest):
    """
    Schedule Agent 실행
    """
    try:
        result = await run_pipeline(kind="schedule", payload=payload.model_dump())
        return ScheduleResponse(
            status="ok",
            plan_csv=result.get("plan_csv"),
            gantt_json=result.get("gantt_json"),
            critical_path=result.get("critical_path"),
            data=result
        )
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/schedule/timeline", response_model=ScheduleResponse)
async def schedule_timeline(project_id: int = Query(..., description="프로젝트 ID")):
    """
    Schedule 타임라인 조회 (project_id 기준)
    """
    try:
        result = await run_pipeline(kind="schedule_timeline", payload={"project_id": project_id})
        return ScheduleResponse(status="ok", data=result)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# -----------------------
# 신규: Workflow (Scope -> Schedule) - 기존 workflow 모듈에서 이전된 엔드포인트
# -----------------------
@router.post("/workflow/scope-then-schedule", response_model=WorkflowResponse)
async def workflow_scope_then_schedule(payload: WorkflowPayload):
    """
    기존 workflow/pm_workflow.py 에 있던 scope_then_schedule 기능을 여기로 통합.
    payload 예시:
    {
      "scope": { ... ScopeRequest ... },
      "schedule": { ... ScheduleRequest ... }
    }
    """
    try:
        result = await run_pipeline(kind="workflow_scope_then_schedule", payload=payload)
        return JSONResponse({"status": "ok", "data": result})

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))