from __future__ import annotations
from datetime import datetime, timedelta, date
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session
from sqlalchemy import and_, func, desc

from server.db import pm_models


def _to_str(dt: Optional[date]) -> Optional[str]:
    if not dt:
        return None
    if isinstance(dt, datetime):
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    return dt.strftime("%Y-%m-%d")


def _row_action_item(ai: "pm_models.PM_ActionItem") -> Dict[str, Any]:
    return {
        "id": ai.id,
        "assignee": ai.assignee,
        "task": ai.task,
        "due_date": _to_str(ai.due_date),
        "priority": ai.priority,
        "status": ai.status,
        "module": ai.module,
        "phase": ai.phase,
        "document_id": ai.document_id,
        "meeting_id": ai.meeting_id,
        "created_at": _to_str(ai.created_at),
    }


def _row_meeting(m: "pm_models.Meeting") -> Dict[str, Any]:
    return {
        "id": m.id,
        "date": _to_str(m.date),
        "title": m.title,
        "created_at": _to_str(m.created_at),
        # raw_text / parsed_json은 부피가 커서 기본 리포트에선 제외
    }


def _row_document(d: "pm_models.PM_Document") -> Dict[str, Any]:
    return {
        "id": d.id,
        "title": d.title,
        "doc_type": d.doc_type,
        "created_at": _to_str(d.created_at),
    }


def build_weekly_report(db: Session, project_id: int, lookback_days: int = 14) -> Dict[str, Any]:
    """
    주간 리포트 빌더
    - 최근 미팅, 최근 등록 문서, 오픈/지각/다가오는 액션아이템 요약
    - 모델명은 실제 정의에 맞게 사용: Meeting (❌ PM_Meeting 아님), PM_ActionItem, PM_Document 등
    """
    today = datetime.utcnow().date()
    since = today - timedelta(days=lookback_days)

    # ---------- 최근 미팅 ----------
    # 모델명 주의! pm_models.Meeting 이 맞음 (이전 코드의 PM_Meeting 오탈자 수정)
    recent_meetings = (
        db.query(pm_models.Meeting)
        .filter(
            pm_models.Meeting.project_id == project_id,
            pm_models.Meeting.date >= since,
        )
        .order_by(desc(pm_models.Meeting.date))
        .limit(10)
        .all()
    )

    # ---------- 최근 문서 ----------
    recent_docs = (
        db.query(pm_models.PM_Document)
        .filter(
            pm_models.PM_Document.project_id == project_id,
            pm_models.PM_Document.created_at >= datetime.combine(since, datetime.min.time()),
        )
        .order_by(desc(pm_models.PM_Document.created_at))
        .limit(10)
        .all()
    )

    # ---------- 액션 아이템 요약 ----------
    # 전체 오픈
    open_items = (
        db.query(pm_models.PM_ActionItem)
        .filter(
            pm_models.PM_ActionItem.project_id == project_id,
            pm_models.PM_ActionItem.status.in_(["Open", "In Progress", "Todo"]),
        )
        .order_by(
            desc(pm_models.PM_ActionItem.priority == "High"),
            pm_models.PM_ActionItem.due_date.is_(None),
            pm_models.PM_ActionItem.due_date.asc(),
        )
        .all()
    )

    # 지각(Overdue)
    overdue_items = (
        db.query(pm_models.PM_ActionItem)
        .filter(
            pm_models.PM_ActionItem.project_id == project_id,
            pm_models.PM_ActionItem.status.in_(["Open", "In Progress", "Todo"]),
            pm_models.PM_ActionItem.due_date.isnot(None),
            pm_models.PM_ActionItem.due_date < today,
        )
        .order_by(pm_models.PM_ActionItem.due_date.asc())
        .all()
    )

    # 이번주 마감 (다음 7일)
    upcoming_items = (
        db.query(pm_models.PM_ActionItem)
        .filter(
            pm_models.PM_ActionItem.project_id == project_id,
            pm_models.PM_ActionItem.status.in_(["Open", "In Progress", "Todo"]),
            pm_models.PM_ActionItem.due_date.isnot(None),
            pm_models.PM_ActionItem.due_date >= today,
            pm_models.PM_ActionItem.due_date < today + timedelta(days=7),
        )
        .order_by(pm_models.PM_ActionItem.due_date.asc())
        .all()
    )

    # 상태별/우선순위별 카운트
    status_counts = dict(
        db.query(pm_models.PM_ActionItem.status, func.count(pm_models.PM_ActionItem.id))
        .filter(pm_models.PM_ActionItem.project_id == project_id)
        .group_by(pm_models.PM_ActionItem.status)
        .all()
    )
    priority_counts = dict(
        db.query(pm_models.PM_ActionItem.priority, func.count(pm_models.PM_ActionItem.id))
        .filter(pm_models.PM_ActionItem.project_id == project_id)
        .group_by(pm_models.PM_ActionItem.priority)
        .all()
    )

    report = {
        "project_id": project_id,
        "generated_at": _to_str(datetime.utcnow()),
        "window_days": lookback_days,
        "meetings_recent": [_row_meeting(m) for m in recent_meetings],
        "documents_recent": [_row_document(d) for d in recent_docs],
        "action_items": {
            "open_total": len(open_items),
            "open_preview": [_row_action_item(ai) for ai in open_items[:20]],
            "overdue": [_row_action_item(ai) for ai in overdue_items[:20]],
            "upcoming_7d": [_row_action_item(ai) for ai in upcoming_items[:20]],
            "status_counts": status_counts,
            "priority_counts": priority_counts,
        },
    }
    return report
