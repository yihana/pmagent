# server/db/pm_crud.py
from __future__ import annotations
from datetime import date, datetime
from typing import Iterable, Optional, Sequence, Dict, Any
from sqlalchemy.orm import Session
from server.db import pm_models
from server.db.database import get_db


# -------------------------
# Project
# -------------------------
def get_or_create_project(db: Session, *, project_id: int, name: Optional[str] = None) -> pm_models.Project:
    proj = db.query(pm_models.Project).filter(pm_models.Project.id == project_id).one_or_none()
    if proj:
        return proj
    proj = pm_models.Project(id=project_id, name=name or f"Project-{project_id}")
    db.add(proj)
    db.commit()
    db.refresh(proj)
    return proj


# -------------------------
# Document
# -------------------------
def create_document(
    db: Session,
    *,
    project_id: int,
    doc_type: str,
    title: Optional[str],
    content: str,
    meta: Optional[dict] = None,
) -> pm_models.PM_Document:
    doc = pm_models.PM_Document(
        project_id=project_id,
        doc_type=doc_type,
        title=title,
        content=content,
        meta=meta or {},
        created_at=datetime.utcnow(),
    )
    db.add(doc)
    db.flush()
    return doc


# -------------------------
# Meeting
# -------------------------
def create_meeting(
    db: Session,
    *,
    project_id: int,
    date_: date,
    title: str,
    raw_text: str,
    parsed_json: Optional[dict] = None,
) -> pm_models.Meeting:
    meeting = pm_models.Meeting(
        project_id=project_id,
        date=date_,
        title=title,
        raw_text=raw_text,
        parsed_json=parsed_json,
        created_at=datetime.utcnow(),
    )
    db.add(meeting)
    db.flush()
    return meeting


# -------------------------
# ActionItem
# -------------------------
def create_action_item(
    db: Session,
    *,
    project_id: int,
    document_id: int,
    task: str,
    assignee: Optional[str] = None,
    due_date: Optional[date] = None,
    priority: Optional[str] = None,
    status: Optional[str] = None,
    module: Optional[str] = None,
    phase: Optional[str] = None,
    evidence_span: Optional[str] = None,
    expected_effort: Optional[str] = None,
    expected_value: Optional[str] = None,
    meeting_id: Optional[int] = None,
) -> pm_models.PM_ActionItem:
    ai = pm_models.PM_ActionItem(
        project_id=project_id,
        document_id=document_id,
        assignee=assignee,
        task=task,
        due_date=due_date,
        priority=priority,
        status=status,
        module=module,
        phase=phase,
        evidence_span=evidence_span,
        expected_effort=expected_effort,
        expected_value=expected_value,
        created_at=datetime.utcnow(),
        meeting_id=meeting_id,
    )
    db.add(ai)
    return ai


def bulk_create_action_items(
    db: Session, *, items: Iterable[pm_models.PM_ActionItem]
) -> Sequence[pm_models.PM_ActionItem]:
    for it in items:
        db.add(it)
    db.flush()
    return list(items)


# -------------------------
# FupItem
# -------------------------
def create_fup_item(
    db: Session,
    *,
    project_id: int,
    document_id: int,
    content: str,
    target: Optional[str] = None,
    owner: Optional[str] = None,
    due_date: Optional[date] = None,
    meeting_id: Optional[int] = None,
) -> pm_models.FupItem:
    f = pm_models.FupItem(
        project_id=project_id,
        document_id=document_id,
        content=content,
        target=target,
        owner=owner,
        due_date=due_date,
        created_at=datetime.utcnow(),
        meeting_id=meeting_id,
    )
    db.add(f)
    return f


# -------------------------
# ✅ Scope Result (PMP 산출물 포함)
# -------------------------
def save_scope_result(
    db: Session,
    *,
    project_id: int,
    scope_json: Dict[str, Any]
) -> pm_models.PM_Scope:
    """Scope Agent 결과 저장 (PMP 표준 산출물 포함)"""
    try:
        scope = pm_models.PM_Scope(
            project_id=project_id,
            scope_statement_md=scope_json.get("scope_statement_md"),
            rtm_csv=scope_json.get("rtm_csv"),
            wbs_json=scope_json.get("wbs_json"),
            # ✅ PMP 산출물
            wbs_excel=scope_json.get("wbs_excel"),
            rtm_excel=scope_json.get("rtm_excel"),
            scope_statement_excel=scope_json.get("scope_statement_excel"),
            project_charter_docx=scope_json.get("project_charter_docx"),
            tailoring_excel=scope_json.get("tailoring_excel"),
            full_json=scope_json
        )
        db.add(scope)
        db.commit()
        db.refresh(scope)
        return scope
    except Exception as e:
        db.rollback()
        print(f"[save_scope_result] Error: {e}")
        raise


# -------------------------
# ✅ Schedule Result (PMP 산출물 포함)
# -------------------------
def save_schedule_result(
    db: Session,
    *,
    project_id: int,
    schedule_json: Dict[str, Any],
    methodology: str = "waterfall"
) -> pm_models.PM_Schedule:
    """Schedule Agent 결과 저장 (PMP 표준 산출물 포함)"""
    try:
        schedule = pm_models.PM_Schedule(
            project_id=project_id,
            methodology=methodology,
            plan_csv=schedule_json.get("plan_csv"),
            gantt_json=schedule_json.get("gantt_json"),
            critical_path=str(schedule_json.get("critical_path")),
            burndown_json=schedule_json.get("burndown_json"),
            # ✅ PMP 산출물
            change_management_excel=schedule_json.get("change_management_excel"),
            full_json=schedule_json
        )
        db.add(schedule)
        db.commit()
        db.refresh(schedule)
        return schedule
    except Exception as e:
        db.rollback()
        print(f"[save_schedule_result] Error: {e}")
        raise


# -------------------------
# ✅ Task 관리
# -------------------------
def save_tasks(
    db: Session,
    *,
    project_id: int,
    tasks: list
) -> list:
    """WBS Task 저장"""
    saved_tasks = []
    for task_data in tasks:
        task = pm_models.PM_Task(
            id=task_data["id"],
            project_id=project_id,
            name=task_data["name"],
            type=task_data.get("type", "task"),
            parent_id=task_data.get("parent_id"),
            duration_days=task_data.get("duration"),
            story_points=task_data.get("story_points"),
            es=task_data.get("ES"),
            ef=task_data.get("EF"),
            ls=task_data.get("LS"),
            lf=task_data.get("LF"),
            float=task_data.get("Float"),
            planned_start=task_data.get("start"),
            planned_end=task_data.get("end"),
            assignee=task_data.get("assignee")
        )
        db.add(task)
        saved_tasks.append(task)
    
    db.commit()
    return saved_tasks


# -------------------------
# ✅ Sprint 관리 (Agile)
# -------------------------
def save_sprint(
    db: Session,
    *,
    project_id: int,
    sprint_no: int,
    start_date: date,
    end_date: date,
    committed_sp: int = 0
) -> pm_models.PM_Sprint:
    """Sprint 정보 저장"""
    sprint = pm_models.PM_Sprint(
        project_id=project_id,
        sprint_no=sprint_no,
        start_date=start_date,
        end_date=end_date,
        committed_sp=committed_sp
    )
    db.add(sprint)
    db.commit()
    db.refresh(sprint)
    return sprint


# -------------------------
# ✅ 산출물 버전 관리
# -------------------------
def save_output_version(
    db: Session,
    *,
    project_id: int,
    version_tag: str,
    output_type: str,
    files_json: Dict[str, str],
    generated_by: Optional[str] = None
) -> pm_models.PM_OutputVersion:
    """산출물 버전 저장"""
    version = pm_models.PM_OutputVersion(
        project_id=project_id,
        version_tag=version_tag,
        output_type=output_type,
        files_json=files_json,
        generated_by=generated_by
    )
    db.add(version)
    db.commit()
    db.refresh(version)
    return version


# -------------------------
# ✅ 이벤트 로그
# -------------------------
def log_event(
    db: Session,
    *,
    event_type: str,
    message: str,
    details: Optional[Dict] = None
) -> pm_models.PM_Log:
    """이벤트 로그 저장"""
    try:
        log = pm_models.PM_Log(
            event_type=event_type,
            message=message,
            details=details
        )
        db.add(log)
        db.commit()
        db.refresh(log)
        return log
    except Exception as e:
        db.rollback()
        print(f"[log_event] Error: {e}")
        raise


# -------------------------
# ✅ 조회 함수들
# -------------------------
def get_latest_scope(db: Session, project_id: int) -> Optional[pm_models.PM_Scope]:
    """최신 Scope 조회"""
    return db.query(pm_models.PM_Scope)\
        .filter(pm_models.PM_Scope.project_id == project_id)\
        .order_by(pm_models.PM_Scope.created_at.desc())\
        .first()


def get_latest_schedule(db: Session, project_id: int) -> Optional[pm_models.PM_Schedule]:
    """최신 Schedule 조회"""
    return db.query(pm_models.PM_Schedule)\
        .filter(pm_models.PM_Schedule.project_id == project_id)\
        .order_by(pm_models.PM_Schedule.created_at.desc())\
        .first()


def get_tasks_by_project(db: Session, project_id: int) -> list:
    """프로젝트의 모든 Task 조회"""
    return db.query(pm_models.PM_Task)\
        .filter(pm_models.PM_Task.project_id == project_id)\
        .all()


def get_sprints_by_project(db: Session, project_id: int) -> list:
    """프로젝트의 모든 Sprint 조회"""
    return db.query(pm_models.PM_Sprint)\
        .filter(pm_models.PM_Sprint.project_id == project_id)\
        .order_by(pm_models.PM_Sprint.sprint_no)\
        .all()