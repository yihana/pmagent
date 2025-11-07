# server/workflow/agents/quality_agent.py

from typing import Any, Dict, List, Optional
import json
import logging

logger = logging.getLogger(__name__)

class QualityAgent:
    """요구사항 품질 검증 Agent"""
    
    def __init__(self, llm=None, threshold: float = 75.0):
        from server.utils.config import get_llm
        self.llm = llm or get_llm()
        self.threshold = threshold
    
    def validate(self, 
                 requirements: List[Dict[str, Any]], 
                 original_text: str,
                 metadata: Optional[Dict] = None) -> Dict[str, Any]:
        """
        요구사항 품질 검증
        
        Returns:
            {
                "pass": bool,
                "score": float,
                "grade": str,
                "metrics": {...},
                "issues": [...],
                "recommendations": [...]
            }
        """
        logger.info(f"🔍 품질 검증 시작 - 요구사항 {len(requirements)}개")
        
        # 1. 구조적 검증 (Rule-based)
        structure_result = self._validate_structure(requirements)
        
        # 2. 의미적 검증 (LLM-based)
        semantic_result = self._validate_semantics(
            requirements, 
            original_text
        )
        
        # 3. 종합 판정
        result = self._aggregate_results(
            structure_result, 
            semantic_result
        )
        
        logger.info(f"✅ 검증 완료 - 점수: {result['score']}, 등급: {result['grade']}")
        
        return result
    
    def _validate_structure(self, requirements: List[Dict]) -> Dict:
        """구조적 검증"""
        score = 0
        max_score = 30
        issues = []
        
        logger.debug("구조적 검증 시작")
        
        # 필수 필드 체크
        required_fields = ['req_id', 'title', 'description', 'type', 
                          'priority', 'source_span']
        
        for req in requirements:
            req_id = req.get('req_id', 'Unknown')
            
            # 1. 필수 필드 존재 (10점)
            missing = [f for f in required_fields if f not in req]
            if not missing:
                score += 10 / len(requirements)
            else:
                issues.append(f"{req_id}: 필드 누락 - {missing}")
            
            # 2. acceptance_criteria 품질 (10점)
            ac = req.get('acceptance_criteria', [])
            if len(ac) >= 2:
                score += 5 / len(requirements)
            else:
                issues.append(f"{req_id}: acceptance_criteria 부족 ({len(ac)}개)")
            
            if ac and all(len(str(c)) > 15 for c in ac):
                score += 5 / len(requirements)
            
            # 3. description 길이 (5점)
            desc = req.get('description', '')
            if len(desc) > 30:
                score += 5 / len(requirements)
            else:
                issues.append(f"{req_id}: description 너무 짧음")
        
        # 4. 타입 분포 (5점)
        types = [r.get('type') for r in requirements]
        if 'functional' in types and 'non-functional' in types:
            score += 5
        
        return {
            "score": min(score, max_score),
            "max_score": max_score,
            "issues": issues
        }
    
    def _validate_semantics(self, 
                           requirements: List[Dict], 
                           original_text: str) -> Dict:
        """의미적 검증 (LLM 사용)"""
        logger.debug("의미적 검증 시작")
        
        prompt = self._build_validation_prompt(requirements, original_text)
        
        try:
            messages = [
                {"role": "system", "content": "You are a requirements quality expert."},
                {"role": "user", "content": prompt}
            ]
            response = self.llm.invoke(messages)
            
            # 응답에서 content 추출
            if hasattr(response, 'content'):
                content = response.content
            else:
                content = str(response)
            
            # JSON 파싱
            result = self._parse_llm_response(content)
            
            logger.info(f"LLM 검증 점수: {result.get('total_score', 0)}")
            
            return result
            
        except Exception as e:
            logger.error(f"LLM 검증 실패: {e}")
            return {
                "score": 0,
                "max_score": 70,
                "issues": [f"LLM 검증 실패: {e}"]
            }
    
    def _build_validation_prompt(self, 
                                 requirements: List[Dict], 
                                 original_text: str) -> str:
        """검증 프롬프트 생성"""
        
        reqs_summary = []
        for r in requirements[:10]:  # 최대 10개만
            reqs_summary.append({
                "req_id": r.get('req_id'),
                "title": r.get('title'),
                "type": r.get('type')
            })
        
        return f"""
다음 요구사항 추출 결과의 품질을 평가하세요.

## 원문 (처음 2000자)
{original_text[:2000]}

## 추출된 요구사항 ({len(requirements)}개)
{json.dumps(reqs_summary, ensure_ascii=False, indent=2)}

## 평가 기준

### 1. Completeness (완성도) - 30점
- 원문의 주요 내용이 빠짐없이 추출되었는가?
- 중요한 요구사항이 누락되지 않았는가?

### 2. Clarity (명확성) - 25점
- 각 요구사항이 명확하고 이해하기 쉬운가?
- 모호한 표현이 없는가?

### 3. Consistency (일관성) - 15점
- 중복된 요구사항이 없는가?
- 모순되는 내용이 없는가?

## 출력 형식 (JSON만)

{{{{
  "completeness_score": 0-30,
  "completeness_issues": ["이슈1", "이슈2"],
  
  "clarity_score": 0-25,
  "clarity_issues": ["이슈1"],
  
  "consistency_score": 0-15,
  "consistency_issues": ["이슈1"],
  
  "total_score": 0-70,
  
  "missing_requirements": [
    "누락된 것으로 보이는 요구사항"
  ],
  
  "recommendations": [
    "REQ-001의 description을 더 구체화하세요",
    "REQ-003과 REQ-004가 유사하여 병합 검토 필요"
  ]
}}}}

JSON만 반환하세요.
"""
    
    def _parse_llm_response(self, content: str) -> Dict:
        """LLM 응답 파싱"""
        try:
            # JSON 추출
            import re
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return {
                    "score": data.get('total_score', 0),
                    "max_score": 70,
                    "completeness": data.get('completeness_score', 0),
                    "clarity": data.get('clarity_score', 0),
                    "consistency": data.get('consistency_score', 0),
                    "issues": (data.get('completeness_issues', []) +
                              data.get('clarity_issues', []) +
                              data.get('consistency_issues', [])),
                    "missing": data.get('missing_requirements', []),
                    "recommendations": data.get('recommendations', [])
                }
        except Exception as e:
            logger.error(f"JSON 파싱 실패: {e}")
        
        return {"score": 0, "max_score": 70, "issues": ["파싱 실패"]}
    
    def _aggregate_results(self, 
                          structure: Dict, 
                          semantic: Dict) -> Dict:
        """결과 통합"""
        
        total_score = structure['score'] + semantic['score']
        max_score = structure['max_score'] + semantic['max_score']
        percentage = (total_score / max_score * 100) if max_score > 0 else 0
        
        # 등급 판정
        if percentage >= 90:
            grade = "Excellent"
            pass_status = True
            action = "accept"
        elif percentage >= 75:
            grade = "Good"
            pass_status = True
            action = "accept_with_warning"
        elif percentage >= 60:
            grade = "Fair"
            pass_status = False
            action = "refinement_required"
        else:
            grade = "Poor"
            pass_status = False
            action = "reject_and_retry"
        
        all_issues = structure['issues'] + semantic.get('issues', [])
        
        return {
            "pass": pass_status,
            "score": round(percentage, 1),
            "grade": grade,
            "action": action,
            "metrics": {
                "structure_score": structure['score'],
                "semantic_score": semantic['score'],
                "total_score": total_score,
                "max_score": max_score
            },
            "issues": all_issues,
            "missing_requirements": semantic.get('missing', []),
            "recommendations": semantic.get('recommendations', [])
        }


# 검증 루프 통합
def extract_with_validation(scope_agent, quality_agent, 
                            text: str, 
                            max_attempts: int = 3,
                            threshold: float = 75.0):
    """검증을 포함한 추출 프로세스"""
    
    for attempt in range(1, max_attempts + 1):
        logger.info(f"📝 추출 시도 #{attempt}")
        
        # 1. 요구사항 추출
        if attempt == 1:
            result = scope_agent.extract_requirements(text)
        else:
            # 이전 검증 결과를 반영하여 재추출
            result = scope_agent.refine_requirements(
                text, 
                previous_result, 
                validation_result
            )
        
        requirements = result.get('requirements', [])
        logger.info(f"✅ {len(requirements)}개 요구사항 추출")
        
        # 2. 품질 검증
        validation_result = quality_agent.validate(requirements, text)
        
        logger.info(f"🎯 품질 점수: {validation_result['score']} "
                   f"({validation_result['grade']})")
        
        # 3. 통과 여부 확인
        if validation_result['pass']:
            logger.info(f"✅ 검증 통과! (시도 {attempt}회)")
            return {
                "success": True,
                "requirements": requirements,
                "validation": validation_result,
                "attempts": attempt
            }
        
        logger.warning(f"⚠️ 검증 실패. 재시도 필요")
        logger.warning(f"주요 이슈: {validation_result['issues'][:3]}")
        
        previous_result = result
    
    # 최대 시도 횟수 초과
    logger.error(f"❌ {max_attempts}회 시도 후에도 검증 실패")
    return {
        "success": False,
        "requirements": requirements,
        "validation": validation_result,
        "attempts": max_attempts
    }