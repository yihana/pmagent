# server/routers/pm_work.py
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, Request, HTTPException, Query, UploadFile, File
from pydantic import BaseModel, Field
import traceback
import shutil
from pathlib import Path
from server.workflow.pm_graph import run_pipeline

router = APIRouter(prefix="/api/v1/pm", tags=["pm"])

# 파일 업로드 디렉토리 설정
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
async def upload_rfp(file: UploadFile = File(...)):
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
    
    응답에 저장된 액션 아이템 수 포함
    """
    try:
        result = await run_pipeline(kind="analyze", payload=payload.model_dump())
        
        # ✅ 저장 직후 바로 액션 아이템 목록 조회
        project_id = result.get("project_id")
        saved_count = result.get("saved_action_items", 0)
        
        # DB에서 방금 저장된 액션 아이템 조회
        action_items_list = []
        if saved_count > 0 and project_id:
            try:
                from server.db.database import SessionLocal
                from server.db import pm_models
                
                db = SessionLocal()
                try:
                    # 방금 저장된 문서의 액션 아이템 조회
                    document_id = result.get("document_id")
                    items = db.query(pm_models.PM_ActionItem)\
                        .filter(pm_models.PM_ActionItem.document_id == document_id)\
                        .all()
                    
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
                finally:
                    db.close()
            except Exception as e:
                logger.warning(f"Failed to fetch action items: {e}")
        
        # 응답 구조 개선
        response_data = {
            "ok": result.get("ok", True),
            "project_id": project_id,
            "document_id": result.get("document_id"),
            "meeting_id": result.get("meeting_id"),
            "saved_action_items": saved_count,
            "action_items": action_items_list,  # ✅ 실제 목록 포함
            "title": payload.title or "Untitled",
            "doc_type": payload.doc_type or "meeting"
        }
        
        return AnalyzeResponse(
            status="ok", 
            data=response_data,
            message=f"분석 완료: {saved_count}개 액션 아이템 저장됨"
        )
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
    """
    Scope Agent 실행
    """
    try:
        result = await run_pipeline(kind="scope", payload=payload.model_dump())
        return ScopeResponse(
            status="ok",
            scope_statement_md=result.get("scope_md_path"),
            rtm_csv=result.get("rtm_csv_path"),
            wbs_json=result.get("wbs_json_path"),
            data=result
        )
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/scope/summary", response_model=ScopeResponse)
async def scope_summary(project_id: int = Query(..., description="프로젝트 ID")):
    """
    Scope 요약 조회 (project_id 기준)
    """
    try:
        result = await run_pipeline(kind="scope_summary", payload={"project_id": project_id})
        return ScopeResponse(status="ok", data=result)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

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
# 신규: Workflow (Scope -> Schedule)
# -----------------------
@router.post("/workflow/scope-then-schedule", response_model=WorkflowResponse)
async def workflow_scope_then_schedule(payload: WorkflowPayload):
    """
    Scope -> Schedule 연계 워크플로우
    payload 예시:
    {
      "scope": { ... ScopeRequest ... },
      "schedule": { ... ScheduleRequest ... }
    }
    """
    try:
        result = await run_pipeline(kind="workflow_scope_then_schedule", payload=payload.model_dump())
        return WorkflowResponse(status="ok", scope=result.get("scope"), schedule=result.get("schedule"))
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))