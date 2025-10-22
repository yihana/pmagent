# server/db/pm_crud.py
from __future__ import annotations
from datetime import date, datetime
from typing import Iterable, Optional, Sequence
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
    db.flush()  # id 확보
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

def save_scope_result(project_name: str, scope_json: dict, methodology: str):
    db: Session = next(get_db())
    try:
        project = db.query(pm_models.PMProject).filter(pm_models.PMProject.name == project_name).first()
        if not project:
            project = pm_models.PMProject(name=project_name, methodology=methodology)
            db.add(project)
            db.commit()
            db.refresh(project)

        scope = pm_models.PMScope(
            project_id=project.id,
            scope_statement_md=scope_json.get("scope_statement_md"),
            rtm_csv=scope_json.get("rtm_csv"),
            wbs_json=scope_json.get("wbs_json"),
            full_json=scope_json
        )
        db.add(scope)
        db.commit()
        db.refresh(scope)
        return scope
    except Exception as e:
        db.rollback()
        print("[save_scope_result] Error:", e)
        return None
    finally:
        db.close()

def save_schedule_result(project_name: str, schedule_json: dict, methodology: str):
    db: Session = next(get_db())
    try:
        project = db.query(pm_models.PMProject).filter(pm_models.PMProject.name == project_name).first()
        if not project:
            project = pm_models.PMProject(name=project_name, methodology=methodology)
            db.add(project)
            db.commit()
            db.refresh(project)

        schedule = pm_models.PMSchedule(
            project_id=project.id,
            plan_csv=schedule_json.get("plan_csv"),
            gantt_json=schedule_json.get("gantt_json"),
            critical_path=str(schedule_json.get("critical_path")),
            full_json=schedule_json
        )
        db.add(schedule)
        db.commit()
        db.refresh(schedule)
        return schedule
    except Exception as e:
        db.rollback()
        print("[save_schedule_result] Error:", e)
        return None
    finally:
        db.close()

def log_event(event_type: str, message: str, details=None):
    db: Session = next(get_db())
    try:
        log = pm_models.PMLog(event_type=event_type, message=message, details=details)
        db.add(log)
        db.commit()
        db.refresh(log)
        return log
    except Exception as e:
        db.rollback()
        print("[log_event] Error:", e)
        return None
    finally:
        db.close()