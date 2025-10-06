from sqlalchemy import Column, Integer, String, Date, DateTime, Text, ForeignKey, JSON, Float
from sqlalchemy.orm import relationship
from datetime import datetime
from server.db.database import Base  # 기존 Base 재사용


class Project(Base):
    __tablename__ = "pm_projects"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    owner = Column(String, nullable=True)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)

    # 역참조
    meetings = relationship("Meeting", back_populates="project")


class PM_ActionItem(Base):
    __tablename__ = "pm_action_items"
    id = Column(Integer, primary_key=True)

    # 기존 필드 유지
    project_id = Column(Integer, index=True, nullable=False)
    document_id = Column(Integer, ForeignKey("pm_documents.id"), nullable=True)
    assignee = Column(String(100), nullable=True)
    task = Column(Text, nullable=False)
    due_date = Column(Date, nullable=True)
    priority = Column(String(10), default="Medium")
    status = Column(String(10), default="Open")
    module = Column(String(10), nullable=True)           # FI, SD, MM, PP, EWM...
    phase = Column(String(20), nullable=True)            # 요구/설계/개발/테스트/인수
    evidence_span = Column(Text, nullable=True)
    expected_effort = Column(Float, nullable=True)       # 인시/MD 등 단위 합의
    expected_value = Column(Float, nullable=True)        # 절감/효익(만원 등)
    created_at = Column(DateTime, default=datetime.utcnow)

    # 🔧 관계 성립을 위해 meeting_id 추가
    meeting_id = Column(Integer, ForeignKey("pm_meetings.id"), index=True, nullable=True)

    # 🔧 Meeting과의 양방향 관계 (lambda로 지연평가)
    meeting = relationship(lambda: Meeting, back_populates="action_items")


class Meeting(Base):
    __tablename__ = "pm_meetings"
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("pm_projects.id"), nullable=False)
    date = Column(Date, nullable=False)
    title = Column(String, nullable=False)
    raw_text = Column(Text, nullable=False)
    parsed_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # 역참조
    project = relationship("Project", back_populates="meetings")

    # 🔧 ActionItem 관계명/역참조 정정 (lambda 사용)
    action_items = relationship(
        lambda: PM_ActionItem,
        back_populates="meeting",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    # 🔧 FupItem 역참조 추가 (기존 FupItem에서 back_populates="fup_items")
    fup_items = relationship(
        lambda: FupItem,
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
    priority = Column(String, nullable=True)  # Low/Med/High
    status = Column(String, default="Open")   # Open/Doing/Done
    evidence_span = Column(Text, nullable=True)

    # 기존 back_populates에 맞춰 Meeting 쪽에도 fup_items 추가함
    meeting = relationship(lambda: Meeting, back_populates="fup_items")


class Risk(Base):
    __tablename__ = "pm_risks"
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, nullable=False)
    source_meeting_id = Column(Integer, ForeignKey("pm_meetings.id"), nullable=True)
    title = Column(String, nullable=False)
    category = Column(String, nullable=True)  # Schedule/Scope/Cost/Quality/Resource/Comm
    cause = Column(String, nullable=True)
    event = Column(String, nullable=True)
    impact_area = Column(JSON, nullable=True) # ["Schedule","Cost"]
    probability = Column(String, nullable=True)   # Low/Med/High
    impact = Column(String, nullable=True)        # Low/Med/High
    proximity = Column(String, nullable=True)
    detectability = Column(String, nullable=True)
    urgency = Column(String, nullable=True)
    controllability = Column(String, nullable=True)
    priority_score = Column(String, nullable=True)
    recommended_responses = Column(JSON, nullable=True)
    status = Column(String, default="Draft")      # Draft/Confirmed/Closed


class PM_Document(Base):
    __tablename__ = "pm_documents"
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, index=True, nullable=False)
    doc_type = Column(String(20), nullable=False)  # meeting, rfp, proposal, issue
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    source_path = Column(String(500), nullable=True)     # 파일경로/원본링크
    created_at = Column(DateTime, default=datetime.utcnow)
    meta = Column(JSON, nullable=True)  # {"uploader": "...", "tags": ["FI","요구"]}


class PM_WeeklyReport(Base):
    __tablename__ = "pm_weekly_reports"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, index=True, nullable=False)
    week_start = Column(Date, nullable=False)
    week_end = Column(Date, nullable=False)
    summary_md = Column(Text, nullable=False)
    snapshot_json = Column(JSON, nullable=True)
    file_path = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class PM_RoiScenario(Base):
    __tablename__ = "pm_roi_scenarios"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, index=True, nullable=False)
    name = Column(String(100), nullable=False)
    # 입력값
    pm_monthly_rate = Column(Float, nullable=False)      # 만원
    monthly_hours = Column(Float, nullable=False)        # 160 등
    months = Column(Integer, nullable=False)             # 6, 12 등
    invest_cost = Column(Float, nullable=False)          # 만원

    analyzer_hours = Column(Float, default=0.0)
    reporter_hours = Column(Float, default=0.0)
    risk_hours = Column(Float, default=0.0)

    # 계산 결과 (캐시)
    monthly_saving_total = Column(Float, default=0.0)    # 만원
    period_saving_total = Column(Float, default=0.0)     # 만원
    roi_percent = Column(Float, default=0.0)             # %
    created_at = Column(DateTime, default=datetime.utcnow)
