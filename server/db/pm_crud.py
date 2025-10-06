from sqlalchemy.orm import Session
from datetime import date
from server.db import pm_models

def create_meeting(db: Session, project_id: int, meeting_date: date, title: str, raw_text: str):
    m = pm_models.Meeting(project_id=project_id, date=meeting_date, title=title, raw_text=raw_text)
    db.add(m); db.commit(); db.refresh(m)
    return m

def save_action_items(db: Session, meeting_id: int, items: list[dict]):
    rows = []
    for it in items:
        row = pm_models.ActionItem(meeting_id=meeting_id, **it)
        db.add(row); rows.append(row)
    db.commit()
    return rows

def latest_actions_by_project(db: Session, project_id: int):
    from server.db import pm_models
    return db.query(pm_models.ActionItem)\
        .join(pm_models.Meeting)\
        .filter(pm_models.Meeting.project_id==project_id)\
        .order_by(pm_models.Meeting.date.desc(), pm_models.ActionItem.id.desc())\
        .all()

def save_risks(db: Session, project_id: int, risks: list[dict], source_meeting_id: int | None=None):
    rows = []
    for r in risks:
        row = pm_models.Risk(project_id=project_id, source_meeting_id=source_meeting_id, **r)
        db.add(row); rows.append(row)
    db.commit()
    return rows

def save_weekly_report(
    db: Session,
    project_id: int,
    week_start: date,
    week_end: date,
    summary_md: str,
    snap: dict | None = None,
    file_path: str | None = None,
):
    snap = snap or {}
    # reporter가 대문자 키(PV/EV/AC/SPI/CPI)를 줄 수도 있고,
    # 기존 코드가 소문자 키를 기대할 수도 있으니 둘 다 안전 처리
    def g(d, *keys, default=0.0):
        for k in keys:
            if k in d:
                return d[k]
        return default

    w = pm_models.WeeklyReport(
        project_id=project_id,
        week_start=week_start,
        week_end=week_end,
        summary_md=summary_md,
        file_path=file_path,
        pv=g(snap, 'pv', 'PV'),
        ev=g(snap, 'ev', 'EV'),
        ac=g(snap, 'ac', 'AC'),
        spi=g(snap, 'spi', 'SPI'),
        cpi=g(snap, 'cpi', 'CPI'),
    )
    db.add(w); db.commit(); db.refresh(w)
    return w
