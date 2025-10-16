from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class Resource(BaseModel):
    role: str
    capacity_pct: int = 100

class Calendar(BaseModel):
    start_date: str
    work_week: List[int] = [1,2,3,4,5]
    holidays: List[str] = []

class ScheduleInput(BaseModel):
    wbs_json: str
    calendar: Calendar
    resource_pool: List[Resource] = []
    sprint_length_weeks: Optional[int] = 2
    estimation_mode: str = 'llm'
    methodology: str = 'waterfall'

class ScheduleOutput(BaseModel):
    plan_csv: str
    gantt_json: str
    critical_path: List[str]
    weekly_reports_dir: str
