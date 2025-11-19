# server/workflow/agents/schedule_agent/got_scheduler.py

from typing import Dict, List, Any, Tuple
import copy
import random

class ScheduleGoT:
    """
    GoT(Graph of Thoughts) 기반 일정 생성기
    기존 ScheduleAgent의 create_schedule() 위에서
    여러 후보 스케줄을 생성하고 평가해 최적안을 선택한다.
    """

    def __init__(self, base_scheduler):
        # base_scheduler = ScheduleAgent()
        self.base = base_scheduler

    # ------------------------------------------------------------
    # ① 후보 스케줄(Thoughts) 생성
    # ------------------------------------------------------------
    def generate_candidates(
        self,
        requirements: List[Dict],
        wbs: List[Dict],
        options: Dict,
        num_candidates: int = 3
    ) -> List[Dict]:
        """
        다양한 파라미터 조합으로 여러 후보 스케줄 생성
        예: 병렬도, 버퍼 전략, 리소스 강도 등 변형
        """
        candidates = []

        for i in range(num_candidates):

            # 예시 파라미터: 병렬도 계수
            parallel_factor = random.choice([0.5, 0.7, 0.9])

            plan = self.base.create_schedule(requirements)

            candidates.append({
                "plan": plan,
                "parallel_factor": parallel_factor,
            })

        return candidates

    # ------------------------------------------------------------
    # ② 후보 평가
    # ------------------------------------------------------------
    def evaluate(self, candidate: Dict) -> float:
        """
        후보 스케줄을 점수화한다.
        기본 예: 기간이 짧고, 일정이 균형적일수록 점수가 높음.
        """
        plan = candidate["plan"]
        duration = plan.get("total_duration", 9999)

        # 기본 점수: 1/duration
        score = 1.0 / max(duration, 1)

        candidate["score"] = score
        return score

    # ------------------------------------------------------------
    # ③ 최적안 선택
    # ------------------------------------------------------------
    def select_best(self, candidates: List[Dict]) -> Tuple[Dict, List[Dict]]:
        scored = []

        for c in candidates:
            score = self.evaluate(c)
            scored.append((score, c))

        scored.sort(key=lambda x: x[0], reverse=True)
        best = scored[0][1]

        return best, scored

    # ------------------------------------------------------------
    # ④ 고수준 실행
    # ------------------------------------------------------------
    def run(self, requirements, wbs, options):
        candidates = self.generate_candidates(requirements, wbs, options)
        best, scored = self.select_best(candidates)

        return {
            "best_plan": best["plan"],
            "candidates": scored
        }
