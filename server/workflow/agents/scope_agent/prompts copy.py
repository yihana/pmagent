# server/agents/scope_agent/prompts.py
SCOPE_EXTRACT_PROMPT = """
당신은 PMP 표준을 준수하는 PMO 분석가입니다.
아래 문서 내용에서 '요구사항, 관련 기능, 예상 산출물, 승인기준'을 구조화해 추출하세요.
- 중복은 병합
- 요구사항은 식별자(REQ-###) 부여
문서:
{context}
출력 JSON 키: requirements[], functions[], deliverables[], acceptance_criteria[]
"""
WBS_SYNTHESIS_PROMPT = """
당신은 PMBOK 5.3/5.4에 따라 WBS를 작성하는 전문가입니다.
입력: 요구사항/기능/산출물 목록, 선택 방법론: {methodology}
규칙:
- Level-1은 방법론에 맞는 단계(예: 분석/설계/개발/테스트 또는 Epic 등)
- 각 하위작업은 특정 산출물/승인기준에 연결
- ID는 1.0, 1.1, 1.2, 2.0 ... 규칙
입력 JSON:
{items}
WBS를 JSON 배열로만 출력하세요. (id,name,parent,deliverable?,acceptance?)
"""
