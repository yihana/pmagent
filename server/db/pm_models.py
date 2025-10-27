# server/db/pm_models.py
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
    path = Column(String(1024), nullable=True)  
    doc_type = Column(String(50), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    uploaded_at = Column(DateTime, default=datetime.utcnow)

    # relations
    project = relationship("Project", back_populates="documents")
    action_items = relationship(
        "PM_ActionItem",
        backref="document",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


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


class PM_ActionItem(Base):
    __tablename__ = "pm_action_items"

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, index=True, nullable=False)
    document_id = Column(Integer, ForeignKey("pm_documents.id"), nullable=True)
    meeting_id = Column(Integer, ForeignKey("pm_meetings.id"), nullable=True)
    
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
    
    meeting = relationship("Meeting", back_populates="action_items")


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


# ✅ Scope Agent 결과 저장
class PM_Scope(Base):
    __tablename__ = "pm_scope"
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, nullable=False)
    scope_statement_md = Column(String(2000))
    rtm_csv = Column(String(1024))
    wbs_json = Column(String(1024))
    
    # ✅ PMP 표준 산출물 경로 추가
    wbs_excel = Column(String(1024), nullable=True)
    rtm_excel = Column(String(1024), nullable=True)
    scope_statement_excel = Column(String(1024), nullable=True)
    project_charter_docx = Column(String(1024), nullable=True)
    tailoring_excel = Column(String(1024), nullable=True)
    
    full_json = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


#1023 Scope agent가 추출한 요구사항을 저장하고, RTM(Requirement-to-WBS/Test) 매핑을 유지하고, 변경요청(CR) 기록, CMP(변경영향분석) 시 사용
class PM_Requirement(Base):
    __tablename__ = "pm_requirements"
    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, index=True, nullable=False)
    req_id = Column(String(50), nullable=False)   # REQ-001 등
    title = Column(String(1000), nullable=False)
    type = Column(String(50), nullable=True)  # functional/non-functional/constraint
    priority = Column(String(20), nullable=True)
    description = Column(Text, nullable=True)
    source_doc = Column(String(1024), nullable=True)  # RFP path or doc id
    status = Column(String(20), default="Draft")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class PM_ChangeRequest(Base):
    __tablename__ = "pm_change_requests"
    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, index=True, nullable=False)
    cr_no = Column(String(50), nullable=False)   # CR-001
    title = Column(String(1000), nullable=False)
    description = Column(Text, nullable=True)
    requested_by = Column(String(100), nullable=True)
    status = Column(String(50), default="Requested")  # Requested/Approved/Rejected/Implemented
    impact = Column(JSON, nullable=True)  # { "tasks": [...], "reqs": [...], "est_days": N }
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class PM_RTM(Base):
    __tablename__ = "pm_rtm"
    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, index=True, nullable=False)
    req_id = Column(String(50), nullable=False)
    wbs_id = Column(String(50), nullable=True)
    test_case = Column(String(1000), nullable=True)
    verification_status = Column(String(50), default="Unmapped")
    created_at = Column(DateTime, default=datetime.utcnow)


# ✅ Schedule Agent 결과 저장
class PM_Schedule(Base):
    __tablename__ = "pm_schedule"
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, nullable=False)
    methodology = Column(String(20), default="waterfall")  # waterfall/agile
    
    # 기본 산출물
    plan_csv = Column(String(1024))
    gantt_json = Column(String(1024))
    critical_path = Column(String(1024))
    burndown_json = Column(String(1024), nullable=True)  # Agile 전용
    
    # ✅ PMP 표준 산출물 경로 추가
    change_management_excel = Column(String(1024), nullable=True)
    
    full_json = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ✅ Task (WBS 아이템별 상세 정보)
class PM_Task(Base):
    __tablename__ = "pm_tasks"
    
    id = Column(String(50), primary_key=True)  # WBS-1.1.2 형태
    project_id = Column(Integer, nullable=False, index=True)
    name = Column(String(500), nullable=False)
    type = Column(String(20))  # phase/task/deliverable
    parent_id = Column(String(50), nullable=True)
    
    # 일정 정보
    duration_days = Column(Integer)
    story_points = Column(Integer, nullable=True)  # Agile 전용
    
    # CPM 계산 결과
    es = Column(Integer)  # Early Start
    ef = Column(Integer)  # Early Finish
    ls = Column(Integer, nullable=True)  # Late Start
    lf = Column(Integer, nullable=True)  # Late Finish
    float = Column(Float, nullable=True)  # Total Float
    
    # 실제 일정
    planned_start = Column(Date, nullable=True)
    planned_end = Column(Date, nullable=True)
    actual_start = Column(Date, nullable=True)
    actual_end = Column(Date, nullable=True)
    
    # 상태
    status = Column(String(20), default="Not Started")  # Not Started/In Progress/Completed
    progress = Column(Integer, default=0)  # 0~100
    assignee = Column(String(100), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)


# ✅ Task 선후행 관계
class PM_TaskLink(Base):
    __tablename__ = "pm_task_links"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, nullable=False, index=True)
    predecessor_id = Column(String(50), nullable=False)
    successor_id = Column(String(50), nullable=False)
    link_type = Column(String(10), default="FS")  # FS/SS/FF/SF
    lag_days = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.utcnow)


# ✅ Sprint (Agile 전용)
class PM_Sprint(Base):
    __tablename__ = "pm_sprints"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, nullable=False, index=True)
    sprint_no = Column(Integer, nullable=False)
    
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    
    committed_sp = Column(Integer, default=0)  # Committed Story Points
    completed_sp = Column(Integer, default=0)  # Completed Story Points
    
    status = Column(String(20), default="Planned")  # Planned/Active/Completed
    
    created_at = Column(DateTime, default=datetime.utcnow)


# ✅ 산출물 버전 관리
class PM_OutputVersion(Base):
    __tablename__ = "pm_output_versions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, nullable=False, index=True)
    version_tag = Column(String(50), nullable=False)  # v1.0, v1.1 등
    output_type = Column(String(50), nullable=False)  # scope/schedule/report
    
    # 생성된 파일 경로들 (JSON)
    files_json = Column(JSON)
    
    generated_at = Column(DateTime, default=datetime.utcnow)
    generated_by = Column(String(100), nullable=True)


# ✅ 이벤트 로그
class PM_Log(Base):
    __tablename__ = "pm_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(String(200))  # scope_generated/schedule_generated/task_updated
    message = Column(Text)
    details = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)