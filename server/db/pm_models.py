from datetime import datetime, date
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Date,
    DateTime,
    Float,
    JSON,
    ForeignKey,
)
from sqlalchemy.orm import relationship

from .database import Base


class Project(Base):
    __tablename__ = "pm_projects"

    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # relations
    documents = relationship(
        "PM_Document",
        back_populates="project",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    meetings = relationship(
        "Meeting",
        back_populates="project",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class PM_Document(Base):
    __tablename__ = "pm_documents"

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("pm_projects.id"), nullable=False)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    # ⚠️ 필드명은 'doc_type' (kind/type 아님)
    doc_type = Column(String(50), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # relations
    project = relationship("Project", back_populates="documents")
    action_items = relationship(
        "PM_ActionItem",
        backref="document",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class PM_ActionItem(Base):
    __tablename__ = "pm_action_items"

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, index=True, nullable=False)
    document_id = Column(Integer, ForeignKey("pm_documents.id"), nullable=True)

    # ✅ 회의 연동 컬럼/관계 (스키마에 meeting_id 존재해야 함)
    meeting_id = Column(Integer, ForeignKey("pm_meetings.id"), nullable=True)
    meeting = relationship("Meeting", back_populates="action_items")

    assignee = Column(String(100), nullable=True)
    task = Column(Text, nullable=False)
    due_date = Column(Date, nullable=True)
    priority = Column(String(10), default="Medium")
    status = Column(String(10), default="Open")
    module = Column(String(10), nullable=True)
    phase = Column(String(20), nullable=True)
    evidence_span = Column(Text, nullable=True)
    expected_effort = Column(Float, nullable=True)
    expected_value = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Meeting(Base):
    __tablename__ = "pm_meetings"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("pm_projects.id"), nullable=False)
    date = Column(Date, nullable=False)
    title = Column(String, nullable=False)
    raw_text = Column(Text, nullable=False)
    parsed_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # relations
    project = relationship("Project", back_populates="meetings")

    # ✅ 역참조 정확히 명시
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


class FupItem(Base):
    __tablename__ = "pm_fup_items"

    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(Integer, ForeignKey("pm_meetings.id"), nullable=False)
    assignee = Column(String, nullable=True)
    task = Column(String, nullable=False)
    due_date = Column(Date, nullable=True)
    priority = Column(String, nullable=True)
    status = Column(String, default="Open")
    evidence_span = Column(Text, nullable=True)

    meeting = relationship("Meeting", back_populates="fup_items")


class Risk(Base):
    __tablename__ = "pm_risks"

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, index=True, nullable=False)
    risk = Column(Text, nullable=False)
    owner = Column(String(100), nullable=True)
    impact = Column(String(20), nullable=True)
    likelihood = Column(String(20), nullable=True)
    mitigation = Column(Text, nullable=True)
    due_date = Column(Date, nullable=True)
    status = Column(String(20), default="Open")
    created_at = Column(DateTime, default=datetime.utcnow)
