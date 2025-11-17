# server/workflow/agents/scope_agent/self_refine.py
from typing import Dict, List, Any, Optional
import logging
import json

logger = logging.getLogger("scope.refine")


class SelfRefineEngine:
    """
    Self-Refine 엔진

    1. 현재 요구사항 목록을 LLM에 보내 'Self-Critique' 받기
    2. 피드백(issues, missing 등)을 기반으로 개선 요청
    3. 개선된 요구사항 목록을 다시 받아 반복

    - llm_caller: prompt(str)를 받아 응답(str)을 리턴하는 함수
      (ScopeAgent에서 self._llm_call_wrapper로 주입):contentReference[oaicite:12]{index=12}
    """

    def __init__(self, llm_caller: Optional[Any] = None) -> None:
        self.llm_caller = llm_caller

        # Self-Critique 프롬프트:contentReference[oaicite:13]{index=13}
        self.critique_prompt_template = """
당신은 요구사항 분석 전문가입니다.
다음 요구사항 목록을 평가하고 개선점을 제시하세요.

평가 기준
- 명확성: 각 요구사항이 명확하고 이해하기 쉬운가?
- 완전성: 모든 필요한 요구사항이 포함되었는가?
- 독립성: 각 요구사항이 독립적으로 구현 가능한가?
- 측정가능성: 검증 기준이 명확한가?

요구사항 목록
{requirements_json}

응답 형식 (JSON)
{{
  "score": 0.85,
  "issues": [
    {{
      "req_id": "REQ-003",
      "problem": "criteria가 모호함",
      "suggestion": "구체적인 수치 기준 추가"
    }}
  ],
  "missing": [
    "보안 요구사항 누락",
    "성능 기준 불명확"
  ],
  "strengths": [
    "기능 요구사항 잘 정리됨"
  ]
}}
"""

        # Refine 프롬프트:contentReference[oaicite:14]{index=14}
        self.refine_prompt_template = """
다음 요구사항 목록을 개선하세요.

현재 요구사항
{requirements_json}

발견된 문제점
{issues}

지시사항
- 문제점을 해결하여 요구사항을 개선하세요
- 누락된 요구사항을 추가하세요
- 중복은 제거하고 병합하세요
- 모호한 부분은 명확히 하세요

응답 형식 (JSON)
{{
  "requirements": [
    {{
      "req_id": "REQ-001",
      "title": "...",
      "type": "functional",
      "priority": "High",
      "description": "...",
      "acceptance_criteria": ["..."]
    }}
  ]
}}
"""

    # ---------- Public API ----------

    def refine_loop(
        self,
        initial_requirements: List[Dict[str, Any]],
        max_iterations: int = 3,
        target_score: float = 0.9,
    ) -> Dict[str, Any]:
        """
        Self-Refine 반복 실행

        Returns:
            {
                "final_requirements": [...],
                "final_score": float,
                "iterations": int,
                "history": [
                    {"iteration": 1, "score": 0.8, "num_requirements": 10},
                    ...
                ]
            }
        """
        if not self.llm_caller:
            logger.warning("[SelfRefine] llm_caller가 설정되지 않아 그대로 반환합니다.")
            return {
                "final_requirements": initial_requirements,
                "final_score": 0.0,
                "iterations": 0,
                "history": [],
            }

        current_reqs = list(initial_requirements)
        current_score = 0.0
        history: List[Dict[str, Any]] = []

        for i in range(1, max_iterations + 1):
            logger.info("[SelfRefine] Iteration %d 시작 (현재 요구사항: %d개)", i, len(current_reqs))

            critique = self._run_critique(current_reqs)
            current_score = critique.get("score", 0.0)

            history.append(
                {
                    "iteration": i,
                    "score": current_score,
                    "num_requirements": len(current_reqs),
                }
            )

            logger.info(
                "[SelfRefine] Iteration %d 결과: score=%.2f",
                i,
                current_score,
            )

            if current_score >= target_score:
                logger.info(
                    "[SelfRefine] 목표 점수(%.2f) 달성, 반복 중단.",
                    target_score,
                )
                break

            # 개선 수행
            issues_for_prompt = {
                "issues": critique.get("issues", []),
                "missing": critique.get("missing", []),
                "strengths": critique.get("strengths", []),
            }
            current_reqs = self._run_refine(current_reqs, issues_for_prompt)

        return {
            "final_requirements": current_reqs,
            "final_score": current_score,
            "iterations": len(history),
            "history": history,
        }

    # ---------- Internal helpers ----------

    def _run_critique(self, requirements: List[Dict[str, Any]]) -> Dict[str, Any]:
        prompt = self.critique_prompt_template.format(
            requirements_json=json.dumps(requirements, ensure_ascii=False, indent=2)
        )
        raw = self._call_llm(prompt)
        try:
            data = json.loads(raw)
        except Exception:
            logger.error("[SelfRefine] critique 응답 JSON 파싱 실패, raw=%r", raw)
            # 최소 형태로 fallback
            return {"score": 0.0, "issues": [], "missing": [], "strengths": []}
        return data

    def _run_refine(
        self,
        requirements: List[Dict[str, Any]],
        issues: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        prompt = self.refine_prompt_template.format(
            requirements_json=json.dumps(requirements, ensure_ascii=False, indent=2),
            issues=json.dumps(issues, ensure_ascii=False, indent=2),
        )
        raw = self._call_llm(prompt)
        try:
            data = json.loads(raw)
            return data.get("requirements", requirements)
        except Exception:
            logger.error("[SelfRefine] refine 응답 JSON 파싱 실패, raw=%r", raw)
            return requirements

    def _call_llm(self, prompt: str) -> str:
        if not self.llm_caller:
            raise ValueError("llm_caller is not set")
        return self.llm_caller(prompt)
