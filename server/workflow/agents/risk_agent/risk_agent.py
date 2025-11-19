# server/workflow/agents/risk_agent/risk_agent.py

from __future__ import annotations
from typing import Any, Dict, List, Optional
import logging

# 기존 규칙 기반 리스크 엔진 재사용
from server.workflow.agents.pm_risk import draft_risks_from_actions

logger = logging.getLogger(__name__)


class RiskAgent:
    """
    High-Level Risk Agent

    - 액션아이템 기반 리스크 초안 생성 (pm_risk.py 재사용)
    - Scope/Cost/Schedule 기반 프로젝트 리스크 Skeleton
    """

    def __init__(self) -> None:
        logger.info("[RiskAgent] initialized")

    # 1) 액션아이템 기반 리스크 생성
    def analyze_actions(self, actions: List[Dict[str, Any]]) -> Dict[str, Any]:
        logger.info("[RiskAgent] 액션아이템 기반 리스크 생성 (n=%d)", len(actions))
        risks = draft_risks_from_actions(actions)
        return {
            "status": "ok",
            "count": len(risks),
            "risks": risks,
        }

    # 2) Scope/Cost/Schedule 기반 프로젝트 리스크 (Skeleton)
    def analyze_project(
        self,
        project_id: str,
        scope: Dict[str, Any],
        cost: Dict[str, Any],
        schedule: Dict[str, Any],
    ) -> Dict[str, Any]:
        req_count = len(scope.get("requirements", []))
        total_cost = cost.get("total_cost", 0)
        cp_days = schedule.get("critical_path_length_days")

        return {
            "project_id": project_id,
            "summary": {
                "requirement_count": req_count,
                "total_cost": total_cost,
                "critical_path_days": cp_days,
            },
            "comments": [
                "Skeleton RiskAgent — 상세 모델은 향후 Monte Carlo/CP 기반으로 확장 예정.",
                "요구사항 수가 많고, CP 길이가 길수록 일정 리스크가 증가할 수 있음.",
            ],
        }

    # 3) 통합 엔드포인트
    def analyze(
        self,
        project_id: str,
        scope: Dict[str, Any],
        cost: Dict[str, Any],
        schedule: Dict[str, Any],
        actions: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        actions = actions or []
        action_risks = self.analyze_actions(actions) if actions else {
            "status": "ok",
            "count": 0,
            "risks": [],
        }
        project_risks = self.analyze_project(project_id, scope, cost, schedule)

        return {
            "status": "ok",
            "action_risks": action_risks,
            "project_risks": project_risks,
        }
