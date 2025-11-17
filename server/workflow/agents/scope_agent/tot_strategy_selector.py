# server/workflow/agents/scope_agent/tot_strategy_selector.py
from typing import Dict, List, Tuple, Optional
import logging

logger = logging.getLogger("scope.tot")


class ToT_StrategySelector:
    """
    Tree of Thoughts 기반 프롬프트 전략 선택기

    - 문서 특성 분석 (길이, 섹션 수, 복잡도)
    - 3가지 전략 평가:
        * Full-Detail  : 고품질, 느림
        * Balanced     : 품질/속도 균형
        * Minimal      : 빠름, 저품질
    - 제약 조건(max_time, min_quality 등)을 고려하여 최적 전략 선택
    """

    def __init__(self) -> None:
        # 전략 정의 (기획 문서 기준):contentReference[oaicite:5]{index=5}
        self.strategies: Dict[str, Dict] = {
            "full_detail": {
                "name": "Full-Detail",
                "description": "모든 예시 포함, 상세 프롬프트",
                "expected_quality": 0.95,
                "expected_time": 120,
                "expected_tokens": 2000,
                "refine_iterations": 5,
                "best_for": "복잡하고 긴 문서 (10+ 섹션)",
            },
            "balanced": {
                "name": "Balanced",
                "description": "Few-shot 예시 2-3개, 균형 프롬프트",
                "expected_quality": 0.90,
                "expected_time": 60,
                "expected_tokens": 1200,
                "refine_iterations": 3,
                "best_for": "일반적인 문서 (5-10 섹션)",
            },
            "minimal": {
                "name": "Minimal",
                "description": "기본 템플릿만, 최소 프롬프트",
                "expected_quality": 0.75,
                "expected_time": 30,
                "expected_tokens": 600,
                "refine_iterations": 1,
                "best_for": "간단한 문서 (5개 미만 섹션)",
            },
        }

    # ---------- Public API ----------

    def select_strategy(
        self,
        text: str,
        constraints: Optional[Dict] = None,
    ) -> Tuple[str, Dict]:
        """
        문서를 분석하고 제약 조건을 고려하여 최적 전략 선택

        Args:
            text: RFP 원문
            constraints: {
                "max_time": int,     # 초 단위
                "min_quality": float # 0~1
            }

        Returns:
            (strategy_key, strategy_dict_with_score_and_rationale)
        """
        constraints = constraints or {}
        doc_info = self.analyze_document(text)
        logger.info(
            "[ToT] 문서 분석 결과: length=%d, sections=%d, complexity=%s",
            doc_info["length"],
            doc_info["num_sections"],
            doc_info["complexity"],
        )

        candidates: List[Tuple[str, Dict, float]] = []

        for key, strategy in self.strategies.items():
            if not self._satisfies_constraints(strategy, constraints):
                continue

            score = self._compute_score(strategy, doc_info, constraints)
            candidates.append((key, strategy, score))

            logger.info(
                "[ToT] 전략 평가: %s | quality=%.2f, time=%ds, score=%.3f",
                strategy["name"],
                strategy["expected_quality"],
                strategy["expected_time"],
                score,
            )

        # 제약조건 모두 위반 시, 전체 중 최고 점수 선택 (완전 망하는 상황 방지)
        if not candidates:
            logger.warning(
                "[ToT] 제약 조건을 만족하는 전략이 없습니다. 모든 전략을 후보로 다시 평가합니다."
            )
            for key, strategy in self.strategies.items():
                score = self._compute_score(strategy, doc_info, constraints or {})
                candidates.append((key, strategy, score))

        # 최고 점수 전략 선택
        best_key, best_strategy, best_score = max(
            candidates, key=lambda x: x[2]
        )

        rationale = self._get_rationale(best_strategy, doc_info)

        result = {
            **best_strategy,
            "score": best_score,
            "rationale": rationale,
            "doc_analysis": doc_info,
        }

        logger.info(
            "[ToT] 선택된 전략: %s (score=%.3f, 이유: %s)",
            result["name"],
            best_score,
            rationale,
        )

        return best_key, result

    # ---------- Document Analysis ----------

    def analyze_document(self, text: str) -> Dict:
        """
        문서 특성 분석

        Returns:
            {
                "length": int,
                "num_sections": int,
                "complexity": "simple" | "medium" | "complex",
                "has_tables": bool
            }
        """  # :contentReference[oaicite:6]{index=6}
        text = text or ""
        length = len(text)

        # 섹션 수 추정 (빈 줄 기준):contentReference[oaicite:7]{index=7}
        sections = [s for s in text.split("\n\n") if s.strip()]
        num_sections = len(sections)

        # 아주 약식 테이블 감지 (| 또는 탭 포함)
        has_tables = ("|" in text) or ("\t" in text)

        # 복잡도 판단 (임계값은 기획 문서의 취지에 맞춰 단순화)
        if length < 3000 and num_sections < 5:
            complexity = "simple"
        elif length < 10000 or num_sections < 10:
            complexity = "medium"
        else:
            complexity = "complex"

        return {
            "length": length,
            "num_sections": num_sections,
            "complexity": complexity,
            "has_tables": has_tables,
        }

    # ---------- Scoring ----------

    def _satisfies_constraints(self, strategy: Dict, constraints: Dict) -> bool:
        max_time = constraints.get("max_time")
        min_quality = constraints.get("min_quality")

        if max_time is not None and strategy["expected_time"] > max_time:
            return False
        if min_quality is not None and strategy["expected_quality"] < min_quality:
            return False
        return True

    def _compute_score(
        self,
        strategy: Dict,
        doc_analysis: Dict,
        constraints: Dict,
    ) -> float:
        """
        전략 점수 계산

        - quality_score: 기대 품질 (0~1)
        - speed_score  : 빠를수록 1에 가까움
        - fit_score    : 문서 복잡도와 전략의 적합도
        - 최종 점수    : 0.5*quality + 0.3*speed + 0.2*fit
        """  # :contentReference[oaicite:8]{index=8}
        quality_score = strategy["expected_quality"]

        # 시간(속도) 점수: 제약이 있으면 그걸 기준, 없으면 180초를 기준으로 clipping
        max_time = constraints.get("max_time", 180)
        speed_score = 1.0 - min(strategy["expected_time"] / max_time, 1.0)

        # 복잡도와의 적합도 (기획 문서 로직 재구성):contentReference[oaicite:9]{index=9}
        complexity = doc_analysis["complexity"]

        if complexity == "simple":
            if strategy["name"] == "Minimal":
                fit_score = 1.0
            elif strategy["name"] == "Balanced":
                fit_score = 0.7
            else:
                fit_score = 0.5
        elif complexity == "medium":
            if strategy["name"] == "Balanced":
                fit_score = 1.0
            elif strategy["name"] == "Minimal":
                fit_score = 0.6
            else:
                fit_score = 0.8
        else:  # complex
            if strategy["name"] == "Full-Detail":
                fit_score = 1.0
            elif strategy["name"] == "Balanced":
                fit_score = 0.8
            else:
                fit_score = 0.4

        total_score = (
            quality_score * 0.5
            + speed_score * 0.3
            + fit_score * 0.2
        )
        return total_score

    def _get_rationale(self, strategy: Dict, doc_analysis: Dict) -> str:
        """
        선택 이유 (사람이 읽을 수 있는 형태) 생성:contentReference[oaicite:10]{index=10}
        """
        reasons: List[str] = []

        # 문서 복잡도 기반
        if doc_analysis["complexity"] == "simple":
            reasons.append("간단한 문서")
        elif doc_analysis["complexity"] == "medium":
            reasons.append("중간 복잡도 문서")
        else:
            reasons.append("복잡한 문서")

        # 전략 장점
        if strategy["name"] == "Full-Detail":
            reasons.append("고품질 필요")
        elif strategy["name"] == "Balanced":
            reasons.append("품질과 속도 균형")
        else:
            reasons.append("빠른 처리 필요")

        return ", ".join(reasons)
