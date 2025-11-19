# server/workflow/agents/pm_integrator.py

from __future__ import annotations
from typing import Any, Dict, List, Optional

import logging
from sqlalchemy.orm import Session

# 기존 분석/리포트 엔진 재사용
from server.workflow.agents.pm_analyzer import PM_AnalyzerAgent
from server.workflow.agents.pm_report import build_weekly_report

# DB 모델
from server.db import pm_models

logger = logging.getLogger(__name__)


class PM_Integrator:
    """
    High-Level 통합 레이어: 회의/문서 → 액션아이템 → 리포트 → (향후) 일정/범위 영향 분석

    기존 pm_analyzer.py + pm_report.py 를 그대로 엔진으로 사용한다.
    """

    def __init__(
        self,
        db: Session,
        model_name: str = "gpt-5",
        temperature: float = 0.2,
    ):
        self.db = db
        self.analyzer = PM_AnalyzerAgent(
            model_name=model_name,
            temperature=temperature,
        )

    # ==========================================================================
    # 1. 회의록 인제스트 → 액션아이템 생성 + 저장
    # ==========================================================================
    def ingest_meeting(
        self,
        project_id: int,
        title: str,
        text: str,
        meta: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        회의록을 입력받아:
         1) Meeting 모델로 저장
         2) PM_AnalyzerAgent로 액션아이템 생성
         3) ActionItem DB로 저장
        """

        logger.info(f"[Integrator] 회의 인제스트 시작: {project_id}, title={title}")

        # -----------------------
        # 1) Meeting 저장
        # -----------------------
        meeting = pm_models.Meeting(
            project_id=project_id,
            title=title,
            raw_text=text,
        )
        self.db.add(meeting)
        self.db.flush()  # meeting.id 확보

        # -----------------------
        # 2) LLM 기반 액션아이템 생성 (재사용)
        # -----------------------
        items = self.analyzer.analyze_minutes(
            text,
            project_meta=meta or {"project_id": project_id},
        )

        # -----------------------
        # 3) DB 저장
        # -----------------------
        created = 0
        for item in items:
            ai = pm_models.PM_ActionItem(
                project_id=project_id,
                meeting_id=meeting.id,
                assignee=item.get("assignee"),
                task=item.get("task"),
                due_date=item.get("due_date"),
                priority=item.get("priority"),
                status=item.get("status"),
                module=item.get("module"),
                phase=item.get("phase"),
            )
            self.db.add(ai)
            created += 1

        self.db.commit()

        logger.info(
            f"[Integrator] 회의 인제스트 완료: meeting_id={meeting.id}, 생성된 AI={created}"
        )

        return {
            "meeting_id": meeting.id,
            "action_items_created": created,
            "items": items,
        }

    # ==========================================================================
    # 2. 문서 인제스트 (보고서/이슈/제안서…)
    # ==========================================================================
    def ingest_document(
        self,
        project_id: int,
        title: str,
        text: str,
        doc_type: str,
        meta: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        일반 문서 인제스트 → 분석 → 문서 테이블 저장
        """

        logger.info(f"[Integrator] 문서 인제스트 시작: {project_id}, type={doc_type}")

        # 1) 문서 저장
        doc = pm_models.PM_Document(
            project_id=project_id,
            title=title,
            raw_text=text,
            doc_type=doc_type,
        )
        self.db.add(doc)
        self.db.flush()

        # 2) 분석 (필요 시)
        if doc_type in ("issue", "report"):
            items = self.analyzer.analyze_issue(
                text, project_meta=meta or {"project_id": project_id}
            )
        else:
            items = []

        # 3) 액션아이템 저장
        for item in items:
            ai = pm_models.PM_ActionItem(
                project_id=project_id,
                document_id=doc.id,
                assignee=item.get("assignee"),
                task=item.get("task"),
                due_date=item.get("due_date"),
                priority=item.get("priority"),
                status=item.get("status"),
            )
            self.db.add(ai)

        self.db.commit()

        return {
            "document_id": doc.id,
            "action_items_created": len(items),
            "items": items,
        }

    # ==========================================================================
    # 3. 주간 스냅샷 조회 (pm_report.py 재사용)
    # ==========================================================================
    def get_weekly_status(
        self, project_id: int, lookback_days: int = 14
    ) -> Dict[str, Any]:
        """
        pm_report.py의 build_weekly_report를 그대로 재사용.
        """

        logger.info(
            f"[Integrator] 주간 상태 조회: project_id={project_id}, lookback={lookback_days}"
        )

        report = build_weekly_report(
            db=self.db,
            project_id=project_id,
            lookback_days=lookback_days,
        )

        return report

    # ==========================================================================
    # 4. 전/후 상태 차이(diff) 계산 (추가 기능)
    # ==========================================================================
    def compare_status(
        self,
        before: Dict[str, Any],
        after: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        pm_report 결과 두 개를 비교하여 '변경 포인트 요약' 생성
        """

        return {
            "open_total_diff": (after["action_items"]["open_total"] -
                                before["action_items"]["open_total"]),
            "overdue_diff": (after["action_items"]["overdue"] -
                             before["action_items"]["overdue"]),
            "priority_diff": {
                "high": after["action_items"]["priority_counts"].get("high", 0)
                        - before["action_items"]["priority_counts"].get("high", 0)
            }
        }
