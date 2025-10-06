from pydantic import BaseModel
from typing import List, Optional
from datetime import date

class MinutesIn(BaseModel):
    project_id: int
    meeting_date: date
    title: str
    text: str

class ActionItemOut(BaseModel):
    assignee: Optional[str] = None
    task: str
    due_date: Optional[date] = None
    priority: Optional[str] = "Medium"
    status: str = "Open"
    module: Optional[str] = None
    phase: Optional[str] = None    
    evidence_span: Optional[str] = None

class AnalyzeResult(BaseModel):
    meeting_id: int
    action_items: List[ActionItemOut]

class RiskOut(BaseModel):
    title: str
    category: str
    cause: Optional[str] = None
    event: Optional[str] = None
    impact_area: List[str] = []
    probability: str
    impact: str
    proximity: Optional[str] = None
    detectability: Optional[str] = None
    urgency: Optional[str] = None
    controllability: Optional[str] = None
    priority_score: Optional[str] = None
    recommended_responses: List[str] = []
    status: str = "Draft"

class ReportOut(BaseModel):
    project_id: int
    week_start: date
    week_end: date
    summary_md: str
    file_path: Optional[str] = None
