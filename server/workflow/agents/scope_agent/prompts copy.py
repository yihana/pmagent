# server/workflow/agents/scope_agent/prompts.py
"""
Scope Agent Prompts - PMP 5.0 Scope Management
"""

# Requirements 추출 프롬프트
SCOPE_EXTRACT_PROMPT = """
당신은 PMP 표준을 준수하는 PMO 분석가입니다.

아래 RFP 문서에서 다음 항목을 구조화하여 추출하세요:

**추출 항목:**

1. **요구사항 (Requirements)**
   - 고유 ID: REQ-001, REQ-002, ... 형식
   - 유형 (type): 
     * functional: 시스템이 수행해야 할 기능
     * non-functional: 성능, 보안, 사용성 등
     * constraint: 제약사항 (예산, 기술 스택, 법규)
   - 우선순위 (priority): High / Medium / Low
   - 설명 (description): 상세 내용
   - 출처 (source_span): RFP 내 위치 (예: "Section 3.2")

2. **기능 (Functions)**
   - 시스템이 제공할 기능 목록
   - 각 기능은 하나 이상의 요구사항과 연결

3. **산출물 (Deliverables)**
   - 프로젝트가 인도할 결과물
   - 형식: docx/pdf/xlsx/system 등
   - 승인 기준 포함

4. **승인 기준 (Acceptance Criteria)**
   - 각 산출물의 검증 기준
   - 관련 요구사항 ID 매핑

**처리 규칙:**

- **중복 제거**: 동일한 의미의 요구사항은 하나로 병합
- **일관성 유지**: 용어 통일 (예: "사용자 인증" vs "로그인" → "사용자 인증"으로 통일)
- **명확성**: 모호한 표현은 구체화
- **추적성**: 원문 위치 명시

**출력 JSON 구조:**

{{
  "requirements": [
    {{
      "req_id": "REQ-001",
      "title": "사용자 인증 기능",
      "type": "functional",
      "priority": "High",
      "description": "사용자는 이메일과 비밀번호를 사용하여 시스템에 로그인할 수 있어야 한다.",
      "source_span": "RFP Section 3.1.1"
    }},
    {{
      "req_id": "REQ-002",
      "title": "응답 시간 성능",
      "type": "non-functional",
      "priority": "High",
      "description": "모든 화면은 2초 이내에 로딩되어야 한다.",
      "source_span": "RFP Section 4.2"
    }},
    {{
      "req_id": "REQ-003",
      "title": "기술 스택 제약",
      "type": "constraint",
      "priority": "High",
      "description": "백엔드는 Python 3.9 이상, 프론트엔드는 React 18 이상을 사용해야 한다.",
      "source_span": "RFP Section 2.3"
    }}
  ],
  
  "functions": [
    {{
      "id": "FUNC-001",
      "title": "회원 관리",
      "description": "회원 가입, 로그인, 프로필 수정 기능",
      "related_requirements": ["REQ-001"]
    }},
    {{
      "id": "FUNC-002",
      "title": "데이터 분석 대시보드",
      "description": "실시간 데이터 시각화 및 리포트 생성",
      "related_requirements": ["REQ-004", "REQ-005"]
    }}
  ],
  
  "deliverables": [
    {{
      "id": "DEL-001",
      "title": "요구사항 정의서",
      "format": "docx",
      "description": "모든 요구사항의 상세 명세",
      "due_phase": "Requirements Analysis"
    }},
    {{
      "id": "DEL-002",
      "title": "시스템 아키텍처 문서",
      "format": "pdf",
      "description": "시스템 구조 및 컴포넌트 다이어그램",
      "due_phase": "Design"
    }},
    {{
      "id": "DEL-003",
      "title": "운영 시스템",
      "format": "system",
      "description": "배포 가능한 완전한 시스템",
      "due_phase": "Deployment"
    }}
  ],
  
  "acceptance_criteria": [
    {{
      "id": "ACC-001",
      "req_id": "REQ-001",
      "criteria": "사용자가 유효한 자격증명으로 로그인 시 대시보드로 이동",
      "verification_method": "테스트 케이스 실행"
    }},
    {{
      "id": "ACC-002",
      "req_id": "REQ-002",
      "criteria": "100명 동시 접속 시 평균 응답 시간 2초 이내",
      "verification_method": "부하 테스트"
    }}
  ]
}}

**문서 내용:**
{context}
"""

# ❌ 제거: WBS는 Schedule Agent에서 생성
# Scope Agent는 Requirements 추출만 담당
RTM_PROMPT = """
당신은 요구사항 추적표(RTM)를 작성하는 전문가입니다.

**목표:** 각 요구사항을 설계, 개발, 테스트 산출물과 매핑

**입력:**
- Requirements: {requirements}
- WBS Nodes (optional): {wbs_nodes}

**매핑 규칙:**

1. **Forward Traceability (순방향 추적)**
   - Requirement → Design → Code → Test Case

2. **Backward Traceability (역방향 추적)**
   - Test Case → Code → Design → Requirement

3. **Coverage 확인**
   - 모든 요구사항이 최소 1개의 테스트 케이스를 가져야 함
   - Orphan 요구사항 (매핑 없음) 식별

**출력 JSON:**
{{
  "mappings": [
    {{
      "req_id": "REQ-001",
      "title": "사용자 인증 기능",
      "design_refs": ["DESIGN-001", "DESIGN-002"],
      "wbs_candidates": ["WBS-1.2.1", "WBS-1.3.1"],
      "test_case_suggestions": ["TC-001", "TC-002"],
      "coverage_status": "full",
      "notes": "Multi-phase implementation"
    }},
    {{
      "req_id": "REQ-002",
      "title": "응답 시간 성능",
      "design_refs": ["DESIGN-005"],
      "wbs_candidates": ["WBS-1.4.2"],
      "test_case_suggestions": ["TC-010"],
      "coverage_status": "partial",
      "notes": "Need performance test automation"
    }}
  ],
  "orphans": ["REQ-099"],
  "warnings": [
    "REQ-002 has only 1 test case (recommend 2+ for NFRs)"
  ],
  "coverage_stats": {{
    "total_requirements": 50,
    "fully_covered": 45,
    "partially_covered": 3,
    "not_covered": 2
  }}
}}
"""

# Scope Statement 생성 프롬프트
SCOPE_STATEMENT_PROMPT = """
다음 정보를 기반으로 프로젝트 범위 기술서(Scope Statement)를 작성하세요:

**프로젝트 정보:**
- 프로젝트명: {project_name}
- 기간: {duration}
- 방법론: {methodology}

**요구사항:**
{requirements}

**산출물:**
{deliverables}

**Scope Statement 구성:**

1. **프로젝트 목적 (Project Justification)**
   - 비즈니스 니즈
   - 기대 효과

2. **범위 설명 (Product Scope Description)**
   - 주요 기능
   - 제품 특성

3. **승인 기준 (Acceptance Criteria)**
   - 완료 조건
   - 품질 기준

4. **산출물 (Deliverables)**
   - 주요 산출물 목록
   - 각 산출물의 승인 기준

5. **제외 사항 (Exclusions)**
   - 명시적으로 제외되는 항목
   - Out of Scope

6. **제약사항 (Constraints)**
   - 예산
   - 일정
   - 기술

7. **가정사항 (Assumptions)**
   - 프로젝트 전제 조건

**출력 형식: Markdown**

# 프로젝트 범위 기술서

## 1. 프로젝트 목적
...

## 2. 범위 설명
...

## 3. 승인 기준
...

## 4. 주요 산출물
...

## 5. 제외 사항
...

## 6. 제약사항
...

## 7. 가정사항
...
"""

# Tailoring 가이드 프롬프트
TAILORING_PROMPT = """
다음 프로젝트 특성에 맞춰 PMP 프로세스를 Tailoring하세요:

**프로젝트 특성:**
- 규모: {size} (소형/중형/대형)
- 방법론: {methodology}
- 복잡도: {complexity} (낮음/중간/높음)
- 팀 크기: {team_size}명
- 기간: {duration}개월

**Tailoring 항목:**

1. **문서화 수준**
   - 소형 프로젝트: 간소화
   - 대형 프로젝트: 완전한 문서

2. **승인 프로세스**
   - 복잡도 낮음: 간소화된 검토
   - 복잡도 높음: 다단계 승인

3. **변경 관리**
   - Agile: 가벼운 변경 프로세스
   - Waterfall: 공식적인 CCB

4. **리스크 관리**
   - 규모에 따른 리스크 레지스터 상세도

**출력 JSON:**
{{
  "documentation": {{
    "level": "standard",
    "required_docs": ["SRS", "Design Doc", "Test Plan"],
    "optional_docs": ["Architecture Decision Records"]
  }},
  "approval_process": {{
    "gates": ["Requirements", "Design", "UAT"],
    "approvers": ["PM", "Tech Lead", "Stakeholder"]
  }},
  "change_management": {{
    "process": "lightweight",
    "approval_threshold": "Medium priority or higher"
  }},
  "risk_management": {{
    "frequency": "bi-weekly",
    "risk_register_detail": "medium"
  }},
  "rationale": "Medium-sized agile project with moderate complexity requires balanced approach"
}}
"""

# Project Charter 생성 프롬프트
PROJECT_CHARTER_PROMPT = """
다음 정보로 프로젝트 헌장(Project Charter)을 작성하세요:

**입력:**
- 프로젝트명: {project_name}
- 스폰서: {sponsor}
- 배경: {background}
- 목표: {objectives}

**Project Charter 구성:**

1. **프로젝트 목적 및 정당성**
2. **측정 가능한 목표 및 성공 기준**
3. **상위 수준 요구사항**
4. **상위 수준 리스크**
5. **요약 마일스톤 일정**
6. **요약 예산**
7. **승인 요구사항**
8. **프로젝트 관리자 임명 및 권한 수준**
9. **스폰서 또는 승인자**

**출력: 구조화된 문서 (Markdown 형식)**
"""