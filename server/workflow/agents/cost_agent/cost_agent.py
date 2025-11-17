# server/workflow/agents/cost_agent/cost_agent.py
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)


class CostAgent:
    """
    비용 추정 Agent (Skeleton)

    - 요구사항 수 + 복잡도 계수 기반 간단 휴리스틱
    """

    def estimate_cost(self, requirements: List[Dict]) -> Dict:
        logger.info("[COST] 비용 추정 시작: %d개 요구사항", len(requirements))

        num_reqs = len(requirements)
        complexity = self._estimate_complexity(requirements)

        base_cost_per_req = 600_000  # 가정값
        total_cost = int(num_reqs * base_cost_per_req * complexity)

        breakdown = {
            "development": int(total_cost * 0.60),
            "testing": int(total_cost * 0.20),
            "management": int(total_cost * 0.20),
        }

        result = {
            "total_cost": total_cost,
            "breakdown": breakdown,
            "assumptions": [
                f"요구사항 {num_reqs}개 기준",
                f"복잡도 계수: {complexity:.2f}",
            ],
            "confidence": 0.7,
            "note": "상세 산정 로직은 향후 WBS 기반으로 교체 예정",
        }

        logger.info("[COST] 완료: 총 %,d원", total_cost)
        return result

    def _estimate_complexity(self, requirements: List[Dict]) -> float:
        high_priority = [
            r for r in requirements if str(r.get("priority", "")).lower() == "high"
        ]
        non_func = [
            r for r in requirements if str(r.get("type", "")).lower()
            in ("non-functional", "nonfunctional")
        ]

        n = len(requirements) or 1
        high_ratio = len(high_priority) / n
        non_func_ratio = len(non_func) / n

        # 복잡도 = 1.0 + (high비율 * 0.5) + (non-func비율 * 0.5):contentReference[oaicite:24]{index=24}
        complexity = 1.0 + high_ratio * 0.5 + non_func_ratio * 0.5
        return min(complexity, 2.0)
