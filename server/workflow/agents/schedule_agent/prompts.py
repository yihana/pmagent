# server/workflow/agents/schedule_agent/prompts.py
"""
Schedule Agent Prompts
- 요구사항 추적표(RTM)
- 일정 계획(WBS Draft)
- 변경관리 지침
"""
DURATION_DEP_PROMPT='''\n입력은 시간정보 없는 WBS입니다. 각 작업의 예상 기간(일)과 선행관계를 제안하세요.
가정:
- 업무 난이도: 보통
- 리소스: 표준 1 FTE 기준
- 방법론: {methodology} (agile이면 2주 스프린트 경계 고려)
출력 JSON 배열: [{id, duration_days, predecessors: [id,...]}]
입력 WBS:
{wbs_json}
'''

# =============================================================================
# 일정 계획 / WBS 보완 프롬프트
# =============================================================================
WBS_SYNTH_PROMPT = '''
당신은 PMP 표준을 준수하는 프로젝트 일정 전문가입니다.

입력으로 주어진 요구사항(requirements)을 기반으로 **WBS(Work Breakdown Structure)**를 설계하세요.
아래 WBS 초안을 기반으로 세부 일정과 기간, 선행 관계를 채워주세요.

### 지침
- Level 1: 프로젝트 전체
- Level 2: 주요 단계 (예: 분석, 설계, 개발, 테스트, 배포)
- Level 3: 구체적 작업 (요구사항 단위 또는 기능 단위)
- 각 노드는 "id", "name", "children" 필드를 포함해야 합니다.

### 입력 요구사항(JSON)
{requirements_json},
{wbs_json}

### 출력 형식(JSON)
{{
  "nodes": [
    {{
      "id": "WBS-1",
      "name": "프로젝트 전체",
      "children": [
        {{
          "id": "WBS-1.1",
          "name": "요구사항 분석",
          "children": [
            {{
              "id": "WBS-1.1.1",
              "name": "REQ-001 이메일 회원가입 기능 구현"
            }}
          ]
        }}
      ]
    }}
  ]
}}

주의:
- **순수 JSON만 반환하세요.**
- WBS 단계는 3단계 이상으로 세분화합니다.
'''

# =============================================================================
# RTM 생성 프롬프트
# =============================================================================
RTM_PROMPT = '''
당신은 PMP 표준을 따르는 테스트 매니저입니다.
아래 요구사항을 기반으로 **요구사항 추적표(RTM)**를 생성하세요.

### 입력 요구사항(JSON)
{requirements_json}

### 작성 지침
- 각 요구사항은 1개 이상의 테스트 케이스로 연결되어야 합니다.
- coverage_status는 "full" | "partial" | "none" 중 하나로 표시합니다.
- 누락된 항목은 "none"으로 표시하고 커버리지 통계에 반영하세요.

### 출력 형식(JSON)
{{
  "mappings": [
    {{
      "req_id": "REQ-001",
      "title": "이메일 회원가입",
      "test_cases": ["TC-001", "TC-002"],
      "coverage_status": "full"
    }}
  ],
  "coverage_statistics": {{
    "total_requirements": 10,
    "fully_covered": 8,
    "coverage_percentage": 80.0
  }}
}}
주의: 순수 JSON만 반환하세요.
'''

# =============================================================================
# 변경관리 지침 (Change Management)
# =============================================================================
CHANGE_MGMT_PROMPT = """
당신은 프로젝트 변경관리 전문가입니다.

아래는 프로젝트의 주요 변경요청 내역입니다. 이를 기반으로 **변경관리표**를 작성하세요.

### 입력 변경요청 내역
{change_requests}

### 출력 JSON
{{
  "changes": [
    {{
      "change_id": "CR-001",
      "title": "요구사항 추가 - 사용자 알림 기능",
      "impact": "일정 +5일, 비용 +2%",
      "decision": "approved",
      "approver": "PMO",
      "approval_date": "2025-02-14"
    }}
  ],
  "summary": {{
    "total_changes": 5,
    "approved": 4,
    "pending": 1
  }}
}}
⚠️ 순수 JSON만 반환하세요.
"""