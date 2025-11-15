# server/db/pm_schemas.py
from __future__ import annotations

from datetime import date, datetime
from typing import Optional, List

from pydantic import BaseModel, Field


# pydantic v2 호환: from_attributes = True (v1의 orm_mode 대체)
class ORMBase(BaseModel):
    model_config = {"from_attributes": True}


# -------------------------
# Project
# -------------------------
class ProjectCreate(BaseModel):
    id: int
    name: str
    description: Optional[str] = None


class ProjectRead(ORMBase):
    id: int
    name: str
    description: Optional[str] = None
    created_at: datetime


# -------------------------
# Document
# -------------------------
class PMDocumentCreate(BaseModel):
    project_id: int
    doc_type: str = Field(default="meeting", description="문서유형 (meeting|report|issue 등)")
    title: Optional[str] = None
    content: str
    meta: Optional[dict] = None


class PMDocumentRead(ORMBase):
    id: int
    project_id: int
    doc_type: str
    title: Optional[str]
    content: str
    meta: Optional[dict]
    created_at: datetime


# -------------------------
# Meeting
# -------------------------
class MeetingCreate(BaseModel):
    project_id: int
    date: date
    title: str
    raw_text: str
    parsed_json: Optional[dict] = None


class MeetingRead(ORMBase):
    id: int
    project_id: int
    date: date
    title: str
    raw_text: str
    parsed_json: Optional[dict]
    created_at: datetime


# -------------------------
# Action Item
# -------------------------
class ActionItemCreate(BaseModel):
    project_id: int
    document_id: int
    task: str
    assignee: Optional[str] = None
    due_date: Optional[date] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    module: Optional[str] = None
    phase: Optional[str] = None
    evidence_span: Optional[str] = None
    expected_effort: Optional[str] = None
    expected_value: Optional[str] = None
    meeting_id: Optional[int] = None


class ActionItemRead(ORMBase):
    id: int
    project_id: int
    document_id: int
    task: str
    assignee: Optional[str]
    due_date: Optional[date]
    priority: Optional[str]
    status: Optional[str]
    module: Optional[str]
    phase: Optional[str]
    evidence_span: Optional[str]
    expected_effort: Optional[str]
    expected_value: Optional[str]
    created_at: datetime
    meeting_id: Optional[int]


# -------------------------
# Follow-up Item
# -------------------------
class FupItemCreate(BaseModel):
    project_id: int
    document_id: int
    content: str
    target: Optional[str] = None
    owner: Optional[str] = None
    due_date: Optional[date] = None
    meeting_id: Optional[int] = None


class FupItemRead(ORMBase):
    id: int
    project_id: int
    document_id: int
    content: str
    target: Optional[str]
    owner: Optional[str]
    due_date: Optional[date]
    created_at: datetime
    meeting_id: Optional[int]

# -------------------------
# scope&schedule agent 스키마 추가
# -------------------------
class PMProjectBase(BaseModel):
    name: str
    methodology: Optional[str] = "waterfall"
    description: Optional[str] = None

class PMProjectCreate(PMProjectBase):
    pass

class PMProject(PMProjectBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


class ScheduleResponse(BaseModel):
    status: str
    message: str
    project_id: str
    methodology: str
    wbs_json_path: Optional[str]
    plan_csv: Optional[str]
    gantt_json: Optional[str]
    timeline: Optional[str]
    burndown_json: Optional[str]
    critical_path: List[str]
    _parsed_critical_path: List[str]
    timeline_tasks: List[Any]
    pmp_outputs: Dict[str, Any]
    data: Dict[str, Any]
    change_requests: Any
