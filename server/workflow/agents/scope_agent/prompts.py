# server/workflow/agents/scope_agent/prompts.py
"""
Scope Agent에서 사용하는 프롬프트 템플릿
주의: Python .format()을 사용하므로, JSON 예시의 중괄호는 {{}}로 이스케이프해야 함
"""

SCOPE_EXTRACT_PROMPT = """
당신은 PMP 표준을 준수하는 PMO 분석가입니다.
아래 문서에서 요구사항(requirements), 관련 기능(functions), 산출물(deliverables), 승인기준(acceptance_criteria)을 구조화하여 JSON으로 추출하세요.
요구사항은 고유 아이디(req_id)를 부여하세요 (예: REQ-001).

출력 예시:
{{
  "requirements": [
    {{
      "req_id": "REQ-001",
      "title": "요구사항 제목",
      "type": "functional",
      "priority": "High",
      "description": "상세 설명",
      "source_span": "문서의 해당 부분"
    }}
  ],
  "functions": [],
  "deliverables": [],
  "acceptance_criteria": []
}}

문서:
{context}
"""

RTM_PROMPT = """
다음 요구사항들에 대한 RTM(Requirements Traceability Matrix) 매핑을 생성하세요.
각 요구사항을 테스트 케이스, 설계 문서, 구현 모듈과 연결하세요.

요구사항:
{{requirements}}

출력 형식: JSON 배열
"""

WBS_SYNTHESIS_PROMPT = """
다음 항목들을 기반으로 WBS(Work Breakdown Structure)를 생성하세요.
각 작업에 대해 ID, 이름, 단계, 예상 기간, 선행 작업을 포함하세요.

항목:
{{items}}

출력 형식: JSON 배열
"""

# 개선/정제 프롬프트
REFINEMENT_PROMPT = """
이전 출력을 개선하세요. 

이전 출력(JSON):
{previous_output}

원문 문서:
{context}

요청: 
1. 누락된 요구사항이 있는지 확인하고 추가
2. 중복된 요구사항 제거
3. 잘못 매핑된 요구사항 수정
4. 각 요구사항에 다음 필드가 있는지 확인:
   - req_id (고유 ID)
   - title (간단한 제목)
   - description (상세 설명)
   - type (functional/non-functional)
   - priority (High/Medium/Low)
   - source_span (문서의 해당 부분)

최종 결과는 JSON으로만 반환하세요.
"""

# 신뢰도 검증 프롬프트
CONFIDENCE_CHECK_PROMPT = """
다음 JSON 출력의 품질을 평가하세요:

{json_output}

평가 기준:
1. 모든 필수 필드가 있는가? (req_id, title, description)
2. 요구사항이 명확하고 구체적인가?
3. 중복이나 모순이 없는가?
4. priority와 type이 적절한가?

신뢰도 점수 (0.0 ~ 1.0)를 반환하세요.
형식: {{"confidence": 0.85, "issues": ["문제점 나열"]}}
"""