# server/routers/pm_work.py
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, Request, HTTPException, Query, UploadFile, File, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
import traceback
import shutil
from pathlib import Path
from datetime import datetime
import json
import csv
import logging
from server.db.database import get_db
from server.db import pm_crud, pm_models
from server.workflow.pm_graph import run_pipeline
from server.utils.doc_reader import read_text_from_path, read_texts, DocReadError

router = APIRouter(prefix="/api/v1/pm", tags=["pm"])
logger = logging.getLogger(__name__)  # ✅ 표준 logging 사용

# 파일 업로드 디렉토리 설정
UPLOAD_DIR = Path("data/inputs/RFP")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
try:
    from server.db.database import SessionLocal
    from server.db import pm_models
    _DB_AVAILABLE = True
except Exception:
    _DB_AVAILABLE = False
    SessionLocal = None
    pm_models = None


# ==== [추가] 출력 폴더 유틸 ====
def _scope_out_dir(project_id: str | int) -> Path:
    """
    Scope 산출물 기본 폴더: <repo-root>/data/outputs/scope/<project_id>
    (프로젝트마다 고정 경로로 저장되도록 통일)
    """
    # server/routers/pm_work.py 기준으로 repo 루트 탐색
    here = Path(__file__).resolve()
    root = here
    for p in here.parents:
        if (p / "data").exists():
            root = p
            break
    out = root / "data" / "outputs" / "scope" / str(project_id)
    out.mkdir(parents=True, exist_ok=True)
    return out


# ==== [추가] 산출물 보정 생성기 ====
def _write_requirements_json(project_id: str | int, requirements: list[dict], source: str = "") -> str:
    out_dir = _scope_out_dir(project_id)
    path = out_dir / "requirements.json"
    payload = {
        "project_id": str(project_id),
        "source": source,
        "generated_at": datetime.utcnow().isoformat(),
        "requirements": requirements or [],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def _write_rtm_csv(project_id: str | int, requirements: list[dict], functions: list[dict] | None = None) -> str:
    """
    간단 round-robin RTM (요구사항 ↔ 기능) 생성.
    기능이 없으면 모두 F-000으로 매핑.
    """
    out_dir = _scope_out_dir(project_id)
    path = out_dir / "rtm.csv"
    fieldnames = ["req_id", "function_id"]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        if not requirements:
            return str(path)
        fn_list = functions or [{"id": "F-000", "title": "Unassigned"}]
        for i, r in enumerate(requirements, start=1):
            req_id = r.get("req_id") or f"REQ-{i:03d}"
            fid = fn_list[(i - 1) % len(fn_list)]["id"]
            writer.writerow({"req_id": req_id, "function_id": fid})
    return str(path)


def _write_srs_md(project_id: str | int, requirements: list[dict], source: str = "") -> str:
    out_dir = _scope_out_dir(project_id)
    path = out_dir / "srs.md"
    lines = [
        f"# SRS (요구사항 명세서)\n",
        f"- project_id: {project_id}",
        f"- source: {source}",
        f"- generated_at: {datetime.utcnow().isoformat()}",
        f"- requirements: {len(requirements or [])} 개\n",
    ]
    for r in (requirements or []):
        rid = r.get("req_id", "")
        ttl = r.get("title", "")
        typ = r.get("type", "")
        pr  = r.get("priority", "")
        src = r.get("source_span", "")
        desc= r.get("description", "")
        lines += [
            f"## {rid} — {ttl}",
            f"- Type: {typ}",
            f"- Priority: {pr}",
            f"- Source: {src}\n",
            desc,
            ""
        ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return str(path)

# ===============================
# 공용 모델
# ===============================

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


# ===============================
# Scope 관련 모델
# ===============================

class DocumentRef(BaseModel):
    path: str
    type: Optional[str] = "RFP"
    name: Optional[str] = None


class ScopeRequest(BaseModel):
    """
    Scope Agent Request
    
    RFP 문서를 제공하는 두 가지 방법:
    1. text: 직접 텍스트 전달 (우선순위 높음)
    2. documents: 파일 경로 리스트
    """
    project_id: Optional[int | str] = Field(default=None, description="프로젝트 ID")
    project_name: Optional[str] = Field(default=None, description="프로젝트명")
    text: Optional[str] = Field(None, description="RFP 텍스트 (직접 전달)")
    documents: Optional[List[DocumentRef]] = Field(default_factory=list, description="RFP 파일 경로 리스트")
    methodology: Optional[str] = Field(default="waterfall", description="방법론: waterfall or agile")
    options: Optional[Dict[str, Any]] = Field(default_factory=dict, description="추가 옵션")
    enable_rag: Optional[bool] = Field(default=True)


class ScopeResponse(BaseModel):
    """Scope Agent Response"""
    status: str
    message: Optional[str] = None
    project_id: str
    
    # 파일 경로
    requirements_json: Optional[str] = None
    srs_path: Optional[str] = None
    rtm_csv: Optional[str] = None
    charter_path: Optional[str] = None
    business_plan_path: Optional[str] = None
    
    # 파싱된 데이터
    requirements: List[Dict[str, Any]] = Field(default_factory=list)
    functions: List[Dict[str, Any]] = Field(default_factory=list)
    deliverables: List[Dict[str, Any]] = Field(default_factory=list)
    acceptance_criteria: List[Dict[str, Any]] = Field(default_factory=list)
    
    # RTM
    rtm_json: Optional[Dict[str, Any]] = None
    
    # ✅ PMP 산출물 (Optional로 None 허용)
    pmp_outputs: Optional[Dict[str, Optional[str]]] = Field(default_factory=dict)
    
    # 통계
    stats: Optional[Dict[str, int]] = None


# ===============================
# Schedule 관련 모델
# ===============================

class CalendarModel(BaseModel):
    start_date: Optional[str] = None
    work_week: Optional[List[int]] = Field(default=[1, 2, 3, 4, 5])
    holidays: Optional[List[str]] = Field(default_factory=list)


class ResourceModel(BaseModel):
    role: str
    capacity_pct: Optional[int] = 100


class ScheduleRequest(BaseModel):
    """
    Schedule Agent Request
    
    WBS 생성 방법:
    1. requirements: Scope Agent 결과 전달 → WBS 자동 생성
    2. wbs_json: 기존 WBS JSON 전달 → 일정만 계산
    """
    project_id: Optional[int | str] = Field(default=None, description="프로젝트 ID")
    
    # WBS 생성용
    requirements: Optional[List[Dict[str, Any]]] = Field(None, description="요구사항 리스트 (WBS 자동 생성)")
    
    # 기존 WBS 사용
    wbs_json: Optional[str] = Field(None, description="WBS JSON (파일 경로 또는 JSON 문자열)")
    
    # 방법론 & 일정 설정
    methodology: Optional[str] = Field(default="waterfall", description="방법론: waterfall or agile")
    calendar: Optional[CalendarModel] = Field(default_factory=CalendarModel, description="캘린더 설정")
    sprint_length_weeks: Optional[int] = Field(default=2, description="Agile: Sprint 길이 (주)")
    
    # Sprint 백로그 (Agile 전용)
    sprint_backlogs: Optional[List[Dict[str, Any]]] = Field(None, description="Sprint 백로그")
    
    # Resource pool
    resource_pool: Optional[List[ResourceModel]] = Field(default_factory=list)
    
    # Change Request
    change_requests: Optional[List[Dict[str, Any]]] = Field(None, description="변경 요청 리스트")
    
    # 추가 옵션
    estimation_mode: Optional[str] = Field(default="heuristic", description="추정 모드: llm or heuristic")


class ScheduleResponse(BaseModel):
    """Schedule Agent Response"""
    status: str
    message: Optional[str] = None
    project_id: str
    methodology: str
    
    # 파일 경로
    wbs_json_path: Optional[str] = None
    plan_csv: Optional[str] = None
    gantt_json: Optional[str] = None
    timeline_path: Optional[str] = None
    burndown_json: Optional[str] = None
    
    # 파싱된 데이터 (list 타입)
    critical_path: List[Dict[str, Any]] = Field(default_factory=list, description="Critical path tasks")
    timeline: List[Dict[str, Any]] = Field(default_factory=list, description="Timeline tasks")
    
    # PMP 산출물
    pmp_outputs: Optional[Dict[str, str]] = None
    
    # 추가 데이터
    data: Optional[Dict[str, Any]] = None
    
    # Change Request 결과
    change_requests: Optional[Dict[str, Any]] = None


# ===============================
# Workflow 모델
# ===============================

class WorkflowRequest(BaseModel):
    """
    통합 Workflow Request (Scope → Schedule)
    """
    project_id: str = Field(..., description="프로젝트 ID")
    text: Optional[str] = Field(None, description="RFP 텍스트")
    documents: Optional[List[DocumentRef]] = Field(default_factory=list, description="RFP 파일 경로")
    methodology: Optional[str] = Field(default="waterfall", description="방법론: waterfall or agile")
    calendar: Optional[CalendarModel] = Field(default_factory=CalendarModel, description="캘린더 설정")
    sprint_length_weeks: Optional[int] = Field(default=2, description="Agile: Sprint 길이 (주)")


class WorkflowResponse(BaseModel):
    """통합 Workflow Response"""
    status: str
    message: Optional[str] = None
    project_id: str
    scope: ScopeResponse
    schedule: ScheduleResponse
    summary: Optional[Dict[str, Any]] = None


# ===============================
# 파일 업로드 엔드포인트
# ===============================

@router.post("/upload/rfp")
async def upload_rfp(file: UploadFile = File(...)):
    """
    RFP PDF 파일 업로드
    - 클라이언트(Streamlit)에서 파일을 업로드받아 서버 경로에 저장
    - 저장된 파일의 서버 경로를 반환하여 Scope/Schedule Agent에서 사용
    """
    try:
        # 파일 확장자 검증
        if not file.filename.lower().endswith(('.pdf', '.txt', '.md')):
            raise HTTPException(
                status_code=400, 
                detail="PDF, TXT, MD 파일만 업로드 가능합니다."
            )
        
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
        raise HTTPException(
            status_code=500, 
            detail=f"파일 업로드 실패: {str(e)}"
        )


# ===============================
# 기존: 그래프 분석 / 리포트
# ===============================

@router.post("/graph/analyze", response_model=AnalyzeResponse)
async def graph_analyze(payload: AnalyzeRequest):
    """
    기존 엔드포인트 유지: 그래프 기반 분석 호출
    회의록 분석 → Action Items 추출 및 DB 저장
    """
    try:
        result = await run_pipeline(kind="analyze", payload=payload.model_dump())
        
        # 저장 직후 바로 액션 아이템 목록 조회
        project_id = result.get("project_id")
        saved_count = result.get("saved_action_items", 0)
        
        # DB에서 방금 저장된 액션 아이템 조회
        action_items_list = []
        if saved_count > 0 and project_id:
            try:
                from server.db.database import SessionLocal
                
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
            "action_items": action_items_list,  # 실제 목록 포함
            "action_items_summary": result.get("action_items"),  # 기존 요약 정보
            "title": payload.title or "Untitled",
            "doc_type": payload.doc_type or "meeting"
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


@router.get("/graph/report", response_model=ReportResponse)
async def graph_report(project_id: int = Query(..., description="프로젝트 ID")):
    """
    기존 리포트 조회 엔드포인트
    """
    try:
        result = await run_pipeline(kind="report", payload={"project_id": project_id})
        return ReportResponse(status="ok", data=result)
    except Exception as e:
        logger.exception(f"[Report] Error: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ===============================
# 신규: Scope Agent (범위관리)
# ===============================

@router.post("/scope/analyze", response_model=ScopeResponse)
async def scope_analyze(request: ScopeRequest):
    """
    Scope Agent: RFP → Requirements 추출
    
    Examples:
        # 1. 텍스트 직접 전달
        {
          "project_id": "P001",
          "text": "RFP 내용...",
          "methodology": "agile"
        }
        
        # 2. 파일 경로 전달
        {
          "project_id": "P001",
          "documents": [{"path": "rfp.txt", "type": "RFP"}],
          "methodology": "waterfall"
        }
    """
    try:
        # Payload 구성
        payload = {
            "project_id": request.project_id or request.project_name or "default",
            "methodology": request.methodology or "waterfall",
        }
        
        # Text or documents
        if request.text:
            payload["text"] = request.text
        elif request.documents:
            payload["documents"] = [doc.model_dump() for doc in request.documents]
        else:
            raise ValueError("Either 'text' or 'documents' must be provided")
        
        # Options
        if request.options:
            payload.update(request.options)
        
        # Scope Agent 실행
        result = await run_pipeline("scope", payload)
        
        if result.get("status") != "ok":
            raise ValueError(result.get("message", "Scope analysis failed"))
        
        return ScopeResponse(
            status=result.get("status", "ok"),
            message=result.get("message"),
            project_id=str(payload["project_id"]),
            
            # 파일 경로
            requirements_json=result.get("requirements_json"),
            srs_path=result.get("srs_path"),
            rtm_csv=result.get("rtm_csv"),
            charter_path=result.get("charter_path"),
            business_plan_path=result.get("business_plan_path"),
            
            # 파싱된 데이터
            requirements=result.get("requirements", []),
            functions=result.get("functions", []),
            deliverables=result.get("deliverables", []),
            acceptance_criteria=result.get("acceptance_criteria", []),
            
            # RTM
            rtm_json=result.get("rtm_json"),
            
            # PMP 산출물
            pmp_outputs=result.get("pmp_outputs"),
            
            # 통계
            stats=result.get("stats")
        )
        
    except ValueError as e:
        logger.error(f"[Scope Agent] Validation Error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"[Scope Agent] Error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Scope analysis failed: {str(e)}"
        )


@router.get("/scope/summary")
async def scope_summary(project_id: str = Query(..., description="프로젝트 ID")):
    """
    Scope 요약 조회 (project_id 기준)
    """
    try:
        result = await run_pipeline(kind="scope_summary", payload={"project_id": project_id})
        return {"status": "ok", "data": result}
    except Exception as e:
        logger.exception(f"[Scope Summary] Error: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ===============================
# 신규: Schedule Agent (일정관리)
# ===============================

@router.post("/schedule/analyze", response_model=ScheduleResponse)
async def schedule_analyze(request: ScheduleRequest):
    """
    Schedule Agent: Requirements → WBS → 일정 계획
    
    Examples:
        # 1. Requirements로 WBS 생성
        {
          "project_id": "P001",
          "requirements": [...],
          "methodology": "agile",
          "calendar": {"start_date": "2025-02-01"}
        }
        
        # 2. 기존 WBS 사용
        {
          "project_id": "P001",
          "wbs_json": "/path/to/wbs.json",
          "methodology": "waterfall"
        }
        
        # 3. Change Request
        {
          "project_id": "P001",
          "wbs_json": "/path/to/wbs.json",
          "change_requests": [
            {"op": "update_duration", "task_id": "WBS-1.1", "new_duration": 10}
          ]
        }
    """
    try:
        # Payload 구성
        payload = {
            "project_id": request.project_id or "default",
            "methodology": request.methodology or "waterfall",
            "calendar": request.calendar.model_dump() if request.calendar else {},
            "sprint_length_weeks": request.sprint_length_weeks or 2,
            "estimation_mode": request.estimation_mode or "heuristic",
        }
        
        # Requirements 또는 WBS JSON
        if request.requirements:
            payload["requirements"] = request.requirements
        elif request.wbs_json:
            payload["wbs_json"] = request.wbs_json
        else:
            raise ValueError("Either 'requirements' or 'wbs_json' must be provided")
        
        # Sprint backlogs (Agile)
        if request.sprint_backlogs:
            payload["sprint_backlogs"] = request.sprint_backlogs
        
        # Change requests
        if request.change_requests:
            payload["change_requests"] = request.change_requests
        
        # Schedule Agent 실행
        result = await run_pipeline("schedule", payload)
        
        if result.get("status") != "ok":
            raise ValueError(result.get("message", "Schedule analysis failed"))
        
        # Critical path 파싱
        critical_path_data = []
        if result.get("_parsed_critical_path"):
            critical_path_data = result["_parsed_critical_path"]
        elif result.get("critical_path") and isinstance(result["critical_path"], str):
            try:
                cp_path = Path(result["critical_path"])
                if cp_path.exists():
                    cp_content = json.loads(cp_path.read_text(encoding="utf-8"))
                    if isinstance(cp_content, dict) and "critical_path" in cp_content:
                        critical_path_data = cp_content["critical_path"]
                    elif isinstance(cp_content, list):
                        critical_path_data = cp_content
            except Exception as e:
                logger.warning(f"Failed to parse critical_path: {e}")
        
        # Timeline 파싱
        timeline_data = []
        if result.get("timeline") and isinstance(result["timeline"], str):
            try:
                timeline_path = Path(result["timeline"])
                if timeline_path.exists():
                    timeline_content = json.loads(timeline_path.read_text(encoding="utf-8"))
                    if isinstance(timeline_content, dict) and "tasks" in timeline_content:
                        timeline_data = timeline_content["tasks"]
                    elif isinstance(timeline_content, list):
                        timeline_data = timeline_content
            except Exception as e:
                logger.warning(f"Failed to parse timeline: {e}")
        
        return ScheduleResponse(
            status="ok",
            message=result.get("message", "Schedule generated successfully"),
            project_id=str(payload["project_id"]),
            methodology=result.get("methodology", payload["methodology"]),
            
            # 파일 경로
            wbs_json_path=result.get("wbs_json_path"),
            plan_csv=result.get("plan_csv"),
            gantt_json=result.get("gantt_json"),
            timeline_path=result.get("timeline"),
            burndown_json=result.get("burndown_json"),
            
            # 파싱된 데이터
            critical_path=critical_path_data,
            timeline=timeline_data,
            
            # PMP 산출물
            pmp_outputs=result.get("pmp_outputs", {}),
            
            # 데이터
            data=result.get("data"),
            
            # Change Request 결과
            change_requests=result.get("change_requests")
        )
        
    except ValueError as e:
        logger.error(f"[Schedule Agent] Validation Error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"[Schedule Agent] Error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Schedule analysis failed: {str(e)}"
        )


@router.get("/schedule/timeline")
async def schedule_timeline(project_id: str = Query(..., description="프로젝트 ID")):
    """
    Schedule 타임라인 조회
    """
    try:
        result = await run_pipeline(
            kind="schedule_timeline", 
            payload={"project_id": project_id}
        )
        return {"status": "ok", "data": result}
    except Exception as e:
        logger.exception(f"[Schedule Timeline] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===============================
# 신규: 통합 Workflow
# ===============================

@router.post("/workflow/scope-schedule", response_model=WorkflowResponse)
async def workflow_scope_then_schedule(request: WorkflowRequest):
    """
    통합 Workflow: Scope → Schedule
    
    Example:
        {
          "project_id": "P001",
          "text": "RFP 내용...",
          "methodology": "agile",
          "calendar": {"start_date": "2025-02-01"},
          "sprint_length_weeks": 2
        }
    """
    try:
        # Payload 구성
        payload = {
            "project_id": request.project_id,
            "methodology": request.methodology or "waterfall",
            "calendar": request.calendar.model_dump() if request.calendar else {},
            "sprint_length_weeks": request.sprint_length_weeks or 2,
        }
        
        # Text or documents
        if request.text:
            payload["text"] = request.text
        elif request.documents:
            payload["documents"] = [doc.model_dump() for doc in request.documents]
        else:
            raise ValueError("Either 'text' or 'documents' must be provided")
        
        # Workflow 실행
        result = await run_pipeline("workflow_scope_then_schedule", payload)
        
        if result.get("status") != "ok":
            raise ValueError(result.get("message", "Workflow failed"))
        
        # Scope 결과 파싱
        scope_result = result.get("scope", {})
        scope_response = ScopeResponse(
            status=scope_result.get("status", "ok"),
            message=scope_result.get("message"),
            project_id=request.project_id,
            requirements_json=scope_result.get("requirements_json"),
            srs_path=scope_result.get("srs_path"),
            rtm_csv=scope_result.get("rtm_csv"),
            charter_path=scope_result.get("charter_path"),
            business_plan_path=scope_result.get("business_plan_path"),
            requirements=scope_result.get("requirements", []),
            functions=scope_result.get("functions", []),
            deliverables=scope_result.get("deliverables", []),
            acceptance_criteria=scope_result.get("acceptance_criteria", []),
            rtm_json=scope_result.get("rtm_json"),
            pmp_outputs=scope_result.get("pmp_outputs"),
            stats=scope_result.get("stats")
        )
        
        # Schedule 결과 파싱
        schedule_result = result.get("schedule", {})
        
        # Critical path
        critical_path_data = schedule_result.get("_parsed_critical_path", [])
        
        # Timeline
        timeline_data = []
        if schedule_result.get("timeline") and isinstance(schedule_result["timeline"], str):
            try:
                timeline_path = Path(schedule_result["timeline"])
                if timeline_path.exists():
                    timeline_content = json.loads(timeline_path.read_text(encoding="utf-8"))
                    if isinstance(timeline_content, dict) and "tasks" in timeline_content:
                        timeline_data = timeline_content["tasks"]
            except Exception:
                pass
        
        schedule_response = ScheduleResponse(
            status=schedule_result.get("status", "ok"),
            message=schedule_result.get("message"),
            project_id=request.project_id,
            methodology=schedule_result.get("methodology", request.methodology),
            wbs_json_path=schedule_result.get("wbs_json_path"),
            plan_csv=schedule_result.get("plan_csv"),
            gantt_json=schedule_result.get("gantt_json"),
            timeline_path=schedule_result.get("timeline"),
            burndown_json=schedule_result.get("burndown_json"),
            critical_path=critical_path_data,
            timeline=timeline_data,
            pmp_outputs=schedule_result.get("pmp_outputs"),
            data=schedule_result.get("data"),
            change_requests=schedule_result.get("change_requests")
        )
        
        return WorkflowResponse(
            status=result.get("status", "ok"),
            message=result.get("message", "Workflow completed successfully"),
            project_id=request.project_id,
            scope=scope_response,
            schedule=schedule_response,
            summary=result.get("summary")
        )
        
    except ValueError as e:
        logger.error(f"[Workflow] Validation Error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"[Workflow] Error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Workflow execution failed: {str(e)}"
        )