# server/db/pm_crud.py
from __future__ import annotations

from datetime import date, datetime
from typing import Iterable, Optional, Sequence

from sqlalchemy.orm import Session

from server.db import pm_models as M


# -------------------------
# Project
# -------------------------
def get_or_create_project(db: Session, *, project_id: int, name: Optional[str] = None) -> M.Project:
    proj = db.query(M.Project).filter(M.Project.id == project_id).one_or_none()
    if proj:
        return proj
    proj = M.Project(id=project_id, name=name or f"Project-{project_id}")
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
) -> M.PM_Document:
    doc = M.PM_Document(
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
) -> M.Meeting:
    meeting = M.Meeting(
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
) -> M.PM_ActionItem:
    ai = M.PM_ActionItem(
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
    db: Session, *, items: Iterable[M.PM_ActionItem]
) -> Sequence[M.PM_ActionItem]:
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
) -> M.FupItem:
    f = M.FupItem(
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
