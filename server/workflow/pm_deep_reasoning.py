# server/workflow/pm_deep_reasoning.py
from typing import Dict

from server.workflow.agents.scope_agent.pipeline import ScopeAgent
from server.workflow.agents.schedule_agent.pipeline import ScheduleAgent
from server.workflow.agents.cost_agent.cost_agent import CostAgent

import logging
import time

logger = logging.getLogger(__name__)


class MinimalPMGraph:
    """
    최소 PM Graph (Demo용)

    Scope (심층추론) → Cost (Skeleton) → Schedule (Skeleton)
    """

    def __init__(self):
        self.scope_agent = ScopeAgent()
        self.cost_agent = CostAgent()
        self.schedule_agent = ScheduleAgent()

    def process(self, document: str) -> Dict:
        logger.info("=" * 70)
        logger.info("🚀 PM GRAPH 시작")
        logger.info("=" * 70)

        start = time.time()

        # Phase 1: Scope
        logger.info("\n[Phase 1/3] Scope Agent 실행")
        logger.info("-" * 70)

        scope_payload = {
            "text": document,
            "project_name": "Demo Project",
            "methodology": "waterfall",
            "options": {
                "tot_constraints": {
                    "max_time": 120,
                    "min_quality": 0.85,
                }
            },
        }
        scope_result = asyncio.run(self.scope_agent.pipeline(scope_payload))
        requirements = scope_result["requirements"]

        logger.info("✅ 요구사항 %d개 추출 완료", len(requirements))

        # Phase 2: Cost
        logger.info("\n[Phase 2/3] Cost Agent 실행")
        logger.info("-" * 70)

        cost_result = self.cost_agent.estimate_cost(requirements)
        logger.info("✅ 비용 추정 완료: %,d원", cost_result["total_cost"])

        # Phase 3: Schedule
        logger.info("\n[Phase 3/3] Schedule Agent 실행")
        logger.info("-" * 70)

        schedule_result = self.schedule_agent.create_schedule(requirements)
        logger.info(
            "✅ 일정 계획 완료: %d일", schedule_result["total_duration"]
        )

        elapsed = time.time() - start

        logger.info("\n" + "=" * 70)
        logger.info("🎉 PM GRAPH 완료 (%.1f초)", elapsed)
        logger.info("=" * 70)

        return {
            "requirements": requirements,
            "cost": cost_result,
            "schedule": schedule_result,
            "execution_time": elapsed,
            "scope_meta": {
                "strategy": scope_result["strategy"],
                "refine": scope_result["refine"],
            },
        }
    
# ------------------------------------------------------------
# 실행 엔트리
# ------------------------------------------------------------
if __name__ == "__main__":
    import asyncio

    logger.setLevel(logging.INFO)
    logging.basicConfig(level=logging.INFO)

    test_text = """
    본 프로젝트는 사용자 로그인, 회원가입, 권한관리 기능을 개발하는 것을 목표로 한다.
    """

    graph = MinimalPMGraph()
    result = graph.process(test_text)

    print("\n=== 최종 결과 ===")
    print(result)

