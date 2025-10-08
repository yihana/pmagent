# server/db/pm_models.py
from __future__ import annotations

from datetime import datetime, date
from typing import Optional

from sqlalchemy import (
    Column,
    Integer,
    String,
    Date,
    DateTime,
    Text,
    ForeignKey,
    JSON,
)
from sqlalchemy.orm import relationship

from server.db.database import Base


# -----------------------------
# Project
# -----------------------------
class Project(Base):
    __tablename__ = "pm_projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relations
    meetings = relationship(
        "Meeting",
        back_populates="project",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    documents = relationship(
        "PM_Document",
        back_populates="project",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    action_items = relationship(
        "PM_ActionItem",
        back_populates="project",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    fup_items = relationship(
        "FupItem",
        back_populates="project",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


# -----------------------------
# Meeting
# -----------------------------
class Meeting(Base):
    __tablename__ = "pm_meetings"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("pm_projects.id"), nullable=False)
    date = Column(Date, nullable=False)
    title = Column(String, nullable=False)
    raw_text = Column(Text, nullable=False)
    parsed_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project", back_populates="meetings")

    # NOTE: 문자열로 클래스명을 적으면 순환 참조/정의 순서 문제를 피할 수 있습니다.
    action_items = relationship(
        "PM_ActionItem",
        back_populates="meeting",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    fup_items = relationship(
        "FupItem",
        back_populates="meeting",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


# -----------------------------
# PM_Document (doc_type 사용: 'type' 충돌 방지)
# -----------------------------
class PM_Document(Base):
    __tablename__ = "pm_documents"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("pm_projects.id"), nullable=False)

    # 'type' 이름은 SQLAlchemy의 다형성에 관여할 수 있어 충돌 여지 → doc_type 로 통일
    doc_type = Column(String, nullable=False, default="meeting")
    title = Column(String, nullable=True)
    content = Column(Text, nullable=False)

    # 메타 / 원본
    meta = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project", back_populates="documents")


# -----------------------------
# Action Item
# -----------------------------
class PM_ActionItem(Base):
    __tablename__ = "pm_action_items"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("pm_projects.id"), nullable=False)
    document_id = Column(Integer, ForeignKey("pm_documents.id"), nullable=False)

    # ✅ 누락으로 에러 나던 컬럼 추가
    meeting_id = Column(Integer, ForeignKey("pm_meetings.id"), nullable=True)

    assignee = Column(String, nullable=True)
    task = Column(Text, nullable=False)

    # SQLite Date는 반드시 python date 객체 필요
    due_date = Column(Date, nullable=True)

    priority = Column(String, nullable=True)  # e.g., High/Medium/Low
    status = Column(String, nullable=True)    # e.g., Open/Closed/In Progress

    module = Column(String, nullable=True)    # e.g., FI/MM/SD ...
    phase = Column(String, nullable=True)     # e.g., 요구/설계/개발/테스트 ...

    evidence_span = Column(Text, nullable=True)
    expected_effort = Column(String, nullable=True)
    expected_value = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project", back_populates="action_items")
    meeting = relationship("Meeting", back_populates="action_items")
    document = relationship("PM_Document")


# -----------------------------
# Follow-up Item
# -----------------------------
class FupItem(Base):
    __tablename__ = "pm_fup_items"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("pm_projects.id"), nullable=False)
    document_id = Column(Integer, ForeignKey("pm_documents.id"), nullable=False)
    meeting_id = Column(Integer, ForeignKey("pm_meetings.id"), nullable=True)

    target = Column(String, nullable=True)
    content = Column(Text, nullable=False)
    owner = Column(String, nullable=True)
    due_date = Column(Date, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project", back_populates="fup_items")
    meeting = relationship("Meeting", back_populates="fup_items")
    document = relationship("PM_Document")
