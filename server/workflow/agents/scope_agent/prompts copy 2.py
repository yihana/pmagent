# server/workflow/agents/scope_agent/prompts.py
"""
Scope Agent Prompts - 계층적 요구사항 추출
Epic → Feature → Requirement 3단계 구조
"""

SCOPE_EXTRACT_PROMPT = """
당신은 PMP 표준을 준수하는 전문 PMO 분석가입니다.

## 🎯 임무
아래 RFP 문서에서 **계층적으로 구조화된** 요구사항을 추출하세요.

## 📊 계층 구조

### Level 1: Epic (대분류)
- **목적**: 주요 기능 영역 또는 비즈니스 도메인
- **대상**: 경영진, 이해관계자 커뮤니케이션
- **개수**: 5-10개 정도
- **예시**: "사용자 관리", "상품 관리", "주문 및 결제"

### Level 2: Feature (중분류)
- **목적**: Epic 내의 구체적 기능 모듈
- **대상**: 스프린트 계획, 일정 관리
- **개수**: Epic당 2-5개
- **예시**: "사용자 인증", "소셜 로그인", "프로필 관리"

### Level 3: Requirement (상세)
- **목적**: 실제 구현 가능한 단위
- **대상**: 개발자 작업 티켓
- **개수**: Feature당 2-5개
- **예시**: "이메일 유효성 검증", "Google OAuth 연동"

## ⚠️ 중요 원칙

### 1. Epic 식별
- 문서의 대분류 섹션 (1단계, 2단계 헤더)
- 기능적으로 관련된 항목들의 그룹
- 비기능 요구사항도 별도 Epic으로 분리
  - 예: "시스템 성능", "보안", "가용성"

### 2. Feature 분해
- Epic 내에서 독립적으로 개발 가능한 모듈
- 사용자 스토리 수준
- 스프린트 하나에서 완료 가능한 범위

### 3. Requirement 세분화
- Feature를 구현하기 위한 구체적 작업
- 독립적으로 테스트 가능
- 명확한 완료 기준 (acceptance criteria)

### 3.1. 요구사항 유형 (type)
- **functional**: 시스템이 수행해야 할 구체적 기능
  - 예: "사용자는 상품을 검색할 수 있어야 한다"
- **non-functional**: 성능, 보안, 사용성, 가용성 등
  - 예: "페이지 로딩은 2초 이내여야 한다"
- **constraint**: 제약사항 (예산, 기술, 법규)
  - 예: "백엔드는 Python/FastAPI를 사용해야 한다"

### 3.2. 우선순위 (priority)
- **High**: 시스템의 핵심 기능, 비즈니스 필수 요소
- **Medium**: 중요하지만 단계적 구현 가능
- **Low**: 부가 기능, 추후 개선 항목

### 3.3. 명확성 원칙
- 모호한 표현 → 구체적으로 변환
  - "빠른 응답" → "1초 이내 응답"
  - "안전한 통신" → "HTTPS 암호화 통신"
- 측정 가능한 기준 포함
- "~할 수 있어야 한다" 형식 사용

### 3.4. 추적성 (source_span)
- 원문의 섹션 번호 또는 제목 명시
- 예: "2.1 사용자 관리", "3.2 보안 요구사항"

## 📋 출력 JSON 구조

{{
  "epics": [
    {{
      "epic_id": "EPIC-001",
      "title": "사용자 관리",
      "description": "사용자의 가입, 인증, 권한 관리 전반",
      "type": "functional",
      "priority": "High",
      "source_span": "2. 기능 요구사항 > 2.1 사용자 관리",
      "business_value": "사용자 기반 확보 및 서비스 접근성 제공",
      
      "features": [
        {{
          "feature_id": "FEAT-001",
          "title": "사용자 인증",
          "description": "이메일 기반 회원가입 및 로그인 기능",
          "priority": "High",
          "story_points": 8,
          
          "requirements": [
            {{
              "req_id": "REQ-001",
              "title": "이메일 회원가입",
              "type": "functional",
              "priority": "High",
              "description": "사용자는 이메일과 비밀번호를 입력하여 계정을 생성할 수 있어야 한다.",
              "acceptance_criteria": [
                "이메일 형식 유효성 검증 (정규식)",
                "중복 이메일 가입 방지 (DB 중복 체크)",
                "비밀번호 최소 8자 이상, 영문+숫자+특수문자 포함",
                "회원가입 완료 시 인증 메일 자동 발송",
                "이메일 인증 완료 전까지 로그인 제한"
              ],
              "estimated_hours": 12,
              "technical_notes": "bcrypt로 비밀번호 해싱, JWT 토큰 발급"
            }},
            {{
              "req_id": "REQ-002",
              "title": "로그인 인증",
              "type": "functional",
              "priority": "High",
              "description": "등록된 사용자는 이메일과 비밀번호로 로그인할 수 있어야 한다.",
              "acceptance_criteria": [
                "이메일/비밀번호 일치 여부 검증",
                "JWT 액세스 토큰 발급 (유효기간 1시간)",
                "리프레시 토큰 발급 (유효기간 30일)",
                "로그인 실패 5회 시 계정 잠금 (10분)",
                "마지막 로그인 시간 기록"
              ],
              "estimated_hours": 8
            }},
            {{
              "req_id": "REQ-003",
              "title": "비밀번호 찾기",
              "type": "functional",
              "priority": "Medium",
              "description": "사용자는 이메일을 통해 비밀번호를 재설정할 수 있어야 한다.",
              "acceptance_criteria": [
                "등록된 이메일로 재설정 링크 발송",
                "링크 유효기간 1시간",
                "링크 클릭 시 새 비밀번호 입력 페이지 이동",
                "재설정 완료 시 기존 세션 모두 무효화"
              ],
              "estimated_hours": 6
            }}
          ]
        }},
        
        {{
          "feature_id": "FEAT-002",
          "title": "소셜 로그인",
          "description": "외부 소셜 계정을 통한 간편 로그인",
          "priority": "High",
          "story_points": 13,
          
          "requirements": [
            {{
              "req_id": "REQ-004",
              "title": "Google OAuth 연동",
              "type": "functional",
              "priority": "High",
              "description": "사용자는 Google 계정으로 로그인할 수 있어야 한다.",
              "acceptance_criteria": [
                "Google OAuth 2.0 프로토콜 구현",
                "구글 로그인 버튼 UI",
                "사용자 정보 (이메일, 이름, 프로필 이미지) 동기화",
                "기존 이메일 계정과 자동 연결",
                "최초 로그인 시 추가 정보 입력 안내"
              ],
              "estimated_hours": 10,
              "technical_notes": "google-auth-library 사용"
            }},
            {{
              "req_id": "REQ-005",
              "title": "Naver OAuth 연동",
              "type": "functional",
              "priority": "High",
              "description": "사용자는 Naver 계정으로 로그인할 수 있어야 한다.",
              "acceptance_criteria": [
                "Naver OAuth API 연동",
                "네이버 아이디로 로그인 버튼",
                "프로필 정보 가져오기"
              ],
              "estimated_hours": 8
            }},
            {{
              "req_id": "REQ-006",
              "title": "Kakao OAuth 연동",
              "type": "functional",
              "priority": "High",
              "description": "사용자는 Kakao 계정으로 로그인할 수 있어야 한다.",
              "acceptance_criteria": [
                "Kakao OAuth API 연동",
                "카카오 로그인 버튼",
                "프로필 정보 가져오기"
              ],
              "estimated_hours": 8
            }}
          ]
        }},
        
        {{
          "feature_id": "FEAT-003",
          "title": "프로필 관리",
          "description": "사용자 정보 조회 및 수정",
          "priority": "Medium",
          "story_points": 5,
          
          "requirements": [
            {{
              "req_id": "REQ-007",
              "title": "프로필 조회",
              "type": "functional",
              "priority": "Medium",
              "description": "사용자는 본인의 프로필 정보를 조회할 수 있어야 한다.",
              "acceptance_criteria": [
                "기본 정보 (이름, 이메일, 전화번호) 표시",
                "프로필 이미지 표시",
                "가입일, 최근 로그인 정보 표시"
              ],
              "estimated_hours": 4
            }},
            {{
              "req_id": "REQ-008",
              "title": "프로필 수정",
              "type": "functional",
              "priority": "Medium",
              "description": "사용자는 본인의 프로필 정보를 수정할 수 있어야 한다.",
              "acceptance_criteria": [
                "닉네임, 전화번호, 주소 수정 가능",
                "프로필 이미지 업로드 (최대 5MB, jpg/png)",
                "이메일 변경 시 재인증 필요",
                "변경 이력 저장 (감사 로그)"
              ],
              "estimated_hours": 8
            }}
          ]
        }}
      ],
      
      "metrics": {{
        "total_features": 3,
        "total_requirements": 8,
        "total_story_points": 26,
        "estimated_hours": 64
      }}
    }},
    
    {{
      "epic_id": "EPIC-002",
      "title": "상품 관리",
      "description": "상품 검색, 조회, 리뷰 기능",
      "type": "functional",
      "priority": "High",
      "source_span": "2.2 상품 관리",
      
      "features": [
        {{
          "feature_id": "FEAT-004",
          "title": "상품 검색 및 필터링",
          "priority": "High",
          "story_points": 13,
          
          "requirements": [
            {{
              "req_id": "REQ-009",
              "title": "키워드 검색",
              "type": "functional",
              "priority": "High",
              "description": "사용자는 상품명으로 상품을 검색할 수 있어야 한다.",
              "acceptance_criteria": [
                "ElasticSearch 전문 검색 엔진 적용",
                "자동완성 기능 (3글자 이상)",
                "오타 교정 기능",
                "검색 결과 관련도순 정렬",
                "검색 키워드 하이라이팅"
              ],
              "estimated_hours": 16
            }},
            {{
              "req_id": "REQ-010",
              "title": "카테고리 필터",
              "type": "functional",
              "priority": "High",
              "description": "사용자는 카테고리별로 상품을 필터링할 수 있어야 한다.",
              "acceptance_criteria": [
                "대/중/소 카테고리 3단계 필터",
                "다중 카테고리 선택 가능",
                "카테고리별 상품 개수 표시"
              ],
              "estimated_hours": 8
            }},
            {{
              "req_id": "REQ-011",
              "title": "가격 및 평점 필터",
              "type": "functional",
              "priority": "Medium",
              "description": "사용자는 가격 범위와 평점으로 상품을 필터링할 수 있어야 한다.",
              "acceptance_criteria": [
                "가격 범위 슬라이더",
                "평점 4점 이상, 3점 이상 등 필터",
                "필터 조합 적용 가능"
              ],
              "estimated_hours": 6
            }}
          ]
        }}
      ]
    }},
    
    {{
      "epic_id": "EPIC-005",
      "title": "시스템 성능",
      "description": "응답 시간, 처리량, 확장성 요구사항",
      "type": "non-functional",
      "priority": "High",
      "source_span": "3.1 성능",
      
      "features": [
        {{
          "feature_id": "FEAT-010",
          "title": "응답 성능",
          "priority": "High",
          
          "requirements": [
            {{
              "req_id": "REQ-030",
              "title": "페이지 로딩 시간",
              "type": "non-functional",
              "priority": "High",
              "description": "모든 페이지는 초기 로딩 시 2초 이내에 표시되어야 한다.",
              "acceptance_criteria": [
                "Lighthouse 성능 점수 90점 이상",
                "First Contentful Paint (FCP) 1.2초 이내",
                "Largest Contentful Paint (LCP) 2.0초 이내",
                "CDN을 통한 정적 자산 배포",
                "이미지 지연 로딩 (lazy loading) 적용"
              ],
              "verification_method": "Lighthouse, WebPageTest"
            }},
            {{
              "req_id": "REQ-031",
              "title": "API 응답 시간",
              "type": "non-functional",
              "priority": "High",
              "description": "모든 API 엔드포인트의 평균 응답 시간은 1초 이내여야 한다.",
              "acceptance_criteria": [
                "95 percentile 응답 시간 1초 이내",
                "99 percentile 응답 시간 2초 이내",
                "데이터베이스 쿼리 최적화 (인덱스 적용)",
                "Redis 캐싱 전략 적용"
              ],
              "verification_method": "JMeter, k6"
            }},
            {{
              "req_id": "REQ-032",
              "title": "동시 접속자 처리",
              "type": "non-functional",
              "priority": "High",
              "description": "최소 1,000명의 동시 접속자를 안정적으로 처리할 수 있어야 한다.",
              "acceptance_criteria": [
                "1,000명 동시 사용자 부하 테스트 통과",
                "에러율 1% 미만",
                "오토 스케일링 정책 설정 (CPU 70% 시)",
                "로드 밸런서 구성 (최소 2대 서버)"
              ],
              "verification_method": "부하 테스트 (JMeter)"
            }}
          ]
        }}
      ]
    }},
    
    {{
      "epic_id": "EPIC-006",
      "title": "보안",
      "description": "데이터 보호, 통신 암호화, 취약점 방어",
      "type": "non-functional",
      "priority": "High",
      "source_span": "3.2 보안",
      
      "features": [
        {{
          "feature_id": "FEAT-011",
          "title": "통신 보안",
          "requirements": [
            {{
              "req_id": "REQ-033",
              "title": "HTTPS 통신 필수",
              "type": "non-functional",
              "priority": "High",
              "description": "모든 클라이언트-서버 간 통신은 HTTPS 프로토콜을 통해 암호화되어야 한다.",
              "acceptance_criteria": [
                "유효한 SSL/TLS 인증서 적용 (Let's Encrypt 또는 유료)",
                "HTTP to HTTPS 자동 리다이렉트",
                "HSTS 헤더 설정 (max-age=31536000)",
                "TLS 1.2 이상 사용"
              ]
            }},
            {{
              "req_id": "REQ-034",
              "title": "개인정보 암호화",
              "type": "non-functional",
              "priority": "High",
              "description": "주민등록번호, 신용카드 정보 등 민감 정보는 암호화하여 저장해야 한다.",
              "acceptance_criteria": [
                "AES-256 암호화 알고리즘 사용",
                "비밀번호는 bcrypt 해싱 (cost factor 12)",
                "암호화 키는 AWS KMS 또는 Vault로 관리",
                "DB 백업 파일도 암호화"
              ]
            }}
          ]
        }},
        {{
          "feature_id": "FEAT-012",
          "title": "취약점 방어",
          "requirements": [
            {{
              "req_id": "REQ-035",
              "title": "SQL Injection 방어",
              "type": "non-functional",
              "priority": "High",
              "description": "SQL Injection 공격으로부터 시스템을 보호해야 한다.",
              "acceptance_criteria": [
                "Parameterized Query 또는 Prepared Statement 사용",
                "ORM 프레임워크 활용 (SQLAlchemy)",
                "입력 값 화이트리스트 검증",
                "에러 메시지에 DB 정보 노출 금지"
              ]
            }},
            {{
              "req_id": "REQ-036",
              "title": "XSS 방어",
              "type": "non-functional",
              "priority": "High",
              "description": "Cross-Site Scripting 공격으로부터 시스템을 보호해야 한다.",
              "acceptance_criteria": [
                "사용자 입력 값 sanitization (DOMPurify)",
                "CSP(Content Security Policy) 헤더 적용",
                "HTML 이스케이핑 자동 적용",
                "innerHTML 대신 textContent 사용"
              ]
            }}
          ]
        }}
      ]
    }},
    
    {{
      "epic_id": "EPIC-007",
      "title": "제약사항",
      "description": "예산, 일정, 기술 스택 제약",
      "type": "constraint",
      "priority": "High",
      "source_span": "4. 제약사항",
      
      "features": [
        {{
          "feature_id": "FEAT-013",
          "title": "기술 제약",
          "requirements": [
            {{
              "req_id": "REQ-040",
              "title": "프론트엔드 기술 스택",
              "type": "constraint",
              "priority": "High",
              "description": "프론트엔드는 React를 사용해야 한다.",
              "acceptance_criteria": [
                "React 18 이상",
                "TypeScript 사용 권장",
                "상태 관리: Redux 또는 Zustand",
                "빌드 도구: Vite 또는 Webpack"
              ]
            }},
            {{
              "req_id": "REQ-041",
              "title": "백엔드 기술 스택",
              "type": "constraint",
              "priority": "High",
              "description": "백엔드는 Python/FastAPI를 사용해야 한다.",
              "acceptance_criteria": [
                "Python 3.9 이상",
                "FastAPI 0.100 이상",
                "비동기 처리 지원 (async/await)",
                "Pydantic 데이터 검증"
              ]
            }},
            {{
              "req_id": "REQ-042",
              "title": "클라우드 인프라",
              "type": "constraint",
              "priority": "High",
              "description": "클라우드는 AWS를 사용해야 한다.",
              "acceptance_criteria": [
                "컴퓨팅: ECS Fargate 또는 EKS",
                "데이터베이스: RDS PostgreSQL",
                "스토리지: S3",
                "CDN: CloudFront"
              ]
            }}
          ]
        }},
        {{
          "feature_id": "FEAT-014",
          "title": "프로젝트 제약",
          "requirements": [
            {{
              "req_id": "REQ-043",
              "title": "예산 제약",
              "type": "constraint",
              "priority": "High",
              "description": "총 프로젝트 예산은 1억원을 초과할 수 없다."
            }},
            {{
              "req_id": "REQ-044",
              "title": "일정 제약",
              "type": "constraint",
              "priority": "High",
              "description": "프로젝트는 6개월 이내에 완료되어야 한다."
            }}
          ]
        }}
      ]
    }}
  ],
  
  "summary": {{
    "total_epics": 7,
    "total_features": 14,
    "total_requirements": 44,
    "by_type": {{
      "functional": 28,
      "non-functional": 12,
      "constraint": 4
    }},
    "by_priority": {{
      "high": 35,
      "medium": 7,
      "low": 2
    }}
  }}
}}

## 📄 문서 내용
{context}

## 🎯 추출 체크리스트
- [ ] Epic은 문서의 대분류를 따르는가?
- [ ] 각 Epic은 2-5개의 Feature를 가지는가?
- [ ] 각 Feature는 2-5개의 Requirement를 가지는가?
- [ ] 비기능 요구사항과 제약사항이 별도 Epic으로 분리되었는가?
- [ ] 각 Requirement가 독립적으로 구현 가능한가?
- [ ] acceptance_criteria가 구체적이고 검증 가능한가?
- [ ] source_span이 명확히 표시되어 있는가?
"""


# =============================================================================
# RTM (Requirements Traceability Matrix) 프롬프트
# =============================================================================

RTM_PROMPT = """
당신은 요구사항 추적표(RTM)를 작성하는 전문가입니다.

## 목표
각 요구사항을 설계, 개발, 테스트 산출물과 매핑하여 추적성을 확보합니다.

## 입력
**요구사항:**
{{requirements}}

**WBS 노드 (선택):**
{{wbs_nodes}}

## 매핑 규칙

### 1. Forward Traceability (순방향 추적)
```
Requirement → Design → Implementation → Test Case
```

### 2. Backward Traceability (역방향 추적)
```
Test Case → Implementation → Design → Requirement
```

### 3. Coverage 원칙
- 모든 요구사항은 최소 1개 이상의 테스트 케이스를 가져야 함
- 비기능 요구사항은 2개 이상의 테스트 케이스 권장
- Orphan 요구사항 (매핑 없음) 식별 및 보고

## 출력 JSON

{{
  "mappings": [
    {{
      "req_id": "REQ-001",
      "title": "이메일 기반 회원가입",
      "design_documents": ["DESIGN-001", "DESIGN-002"],
      "implementation_refs": ["auth/signup.py", "auth/validation.py"],
      "test_cases": ["TC-001", "TC-002", "TC-003"],
      "wbs_tasks": ["WBS-1.2.1", "WBS-1.2.2"],
      "coverage_status": "full",
      "notes": "Phase 1 구현 완료"
    }},
    {{
      "req_id": "REQ-002",
      "title": "소셜 로그인 통합",
      "design_documents": ["DESIGN-003"],
      "implementation_refs": ["auth/oauth.py"],
      "test_cases": ["TC-004"],
      "wbs_tasks": ["WBS-1.2.3"],
      "coverage_status": "partial",
      "notes": "Google OAuth만 구현, Naver/Kakao 추가 필요"
    }}
  ],
  
  "orphans": [
    {{
      "req_id": "REQ-099",
      "title": "데이터 익명화",
      "reason": "테스트 케이스 미작성"
    }}
  ],
  
  "warnings": [
    "REQ-002: 소셜 로그인 일부만 구현됨 (Google only)",
    "REQ-015: 성능 테스트 케이스가 1개만 존재 (최소 2개 권장)"
  ],
  
  "coverage_statistics": {{
    "total_requirements": 50,
    "fully_covered": 42,
    "partially_covered": 5,
    "not_covered": 3,
    "coverage_percentage": 84.0
  }}
}}
"""

# =============================================================================
# WBS 생성 프롬프트 (제거 - Schedule Agent로 이관)
# =============================================================================

# WBS는 Schedule Agent에서 생성하므로 Scope Agent에서는 제거
# 단, RTM에서 WBS 참조는 가능 (wbs_candidates 필드)

WBS_SYNTHESIS_PROMPT = """
⚠️ 경고: WBS 생성은 Schedule Agent의 역할입니다.
Scope Agent는 Requirements 추출과 RTM 생성만 담당합니다.

WBS가 필요한 경우 Schedule Agent를 호출하세요.
"""

# =============================================================================
# Scope Statement 생성 프롬프트
# =============================================================================

SCOPE_STATEMENT_PROMPT = """
다음 정보를 기반으로 프로젝트 범위 기술서(Scope Statement)를 작성하세요.

## 프로젝트 정보
- **프로젝트명**: {{project_name}}
- **기간**: {{duration}}
- **방법론**: {{methodology}}
- **예산**: {{budget}}

## 요구사항
{{requirements}}

## 산출물
{{deliverables}}

---

# 프로젝트 범위 기술서 (Project Scope Statement)

## 1. 프로젝트 목적 및 정당성 (Project Justification)

### 1.1 비즈니스 니즈
[비즈니스 문제 또는 기회 설명]

### 1.2 기대 효과
- 정량적 효과: [ROI, 비용 절감 등]
- 정성적 효과: [고객 만족도, 브랜드 가치 등]

## 2. 제품 범위 설명 (Product Scope Description)

### 2.1 주요 기능
1. [기능 1]
2. [기능 2]
3. [기능 3]

### 2.2 제품 특성
- [특성 1]
- [특성 2]

## 3. 승인 기준 (Acceptance Criteria)

### 3.1 완료 조건
- [ ] 모든 High 우선순위 요구사항 구현
- [ ] 성능 테스트 통과
- [ ] UAT 완료

### 3.2 품질 기준
- 코드 커버리지: 80% 이상
- 버그 밀도: Critical 0건, Major 5건 이하
- 성능: SLA 기준 만족

## 4. 주요 산출물 (Project Deliverables)

| ID | 산출물명 | 형식 | 인도 단계 | 승인 기준 |
|----|---------|------|----------|----------|
| DEL-001 | 요구사항 명세서 | docx | 요구분석 | 이해관계자 승인 |
| DEL-002 | 시스템 아키텍처 | pdf | 설계 | 기술 검토 통과 |
| DEL-003 | 운영 시스템 | system | 구축 | UAT 통과 |

## 5. 제외 사항 (Project Exclusions)

**명시적으로 범위에서 제외되는 항목:**
- [제외 항목 1]
- [제외 항목 2]

## 6. 제약사항 (Constraints)

### 6.1 예산 제약
- 총 예산: {{budget}}
- 예산 초과 시 변경 요청 필요

### 6.2 일정 제약
- 프로젝트 기간: {{duration}}
- 고정 마일스톤: [날짜]

### 6.3 기술 제약
- 기술 스택: [지정된 기술]
- 레거시 시스템 연동 필요

### 6.4 리소스 제약
- 팀 크기: [인원]
- 외부 협력사 의존성

## 7. 가정사항 (Assumptions)

- 가정 1: [전제 조건]
- 가정 2: [전제 조건]
- 가정 3: [전제 조건]

## 8. 승인

| 역할 | 이름 | 서명 | 날짜 |
|-----|------|------|------|
| 프로젝트 스폰서 | | | |
| 프로젝트 관리자 | | | |
| 기술 리드 | | | |

---

**작성일**: {{generated_date}}
**문서 버전**: 1.0
"""

# =============================================================================
# 정제 프롬프트 (Refinement)
# =============================================================================

REFINEMENT_PROMPT = """
이전 추출 결과를 개선하세요.

## 이전 출력 (JSON)
{{previous_output}}

## 원문 문서
{{context}}

## 개선 요청사항

### 1. 누락 확인
- 문서에 있지만 추출되지 않은 요구사항 찾기
- 특히 비기능 요구사항 누락 여부 확인

### 2. 중복 제거
- 동일하거나 유사한 요구사항 병합
- 병합 시 더 구체적인 설명 유지

### 3. 세분화 재검토
- 하나의 요구사항에 여러 기능이 포함되어 있는지 확인
- 필요 시 개별 요구사항으로 분리

### 4. 명확성 개선
- 모호한 표현을 구체적으로 변경
- 측정 가능한 기준 추가

### 5. 필수 필드 확인
각 요구사항이 다음 필드를 모두 가지고 있는지 확인:
- ✅ req_id (고유 ID)
- ✅ title (간단한 제목)
- ✅ description (상세 설명)
- ✅ type (functional/non-functional/constraint)
- ✅ priority (High/Medium/Low)
- ✅ source_span (문서의 해당 부분)
- ✅ acceptance_criteria (배열, 최소 2개 이상)

## 출력 형식
JSON으로만 반환하세요. 설명이나 주석 없이 순수 JSON만 출력하세요.
"""

# =============================================================================
# 신뢰도 검증 프롬프트
# =============================================================================

CONFIDENCE_CHECK_PROMPT = """
다음 JSON 출력의 품질을 평가하세요.

## 추출 결과
{{json_output}}

## 평가 기준

### 1. 완성도 (Completeness)
- [ ] 모든 필수 필드 존재 (req_id, title, description, type, priority, source_span)
- [ ] acceptance_criteria가 구체적이고 측정 가능
- [ ] 문서의 주요 요구사항이 모두 추출됨

### 2. 명확성 (Clarity)
- [ ] 요구사항 설명이 구체적이고 이해하기 쉬움
- [ ] 모호한 표현이 없음
- [ ] 기술 용어가 일관되게 사용됨

### 3. 일관성 (Consistency)
- [ ] 중복이나 모순이 없음
- [ ] 유사한 요구사항의 표현 방식이 일관됨
- [ ] priority 부여가 합리적임

### 4. 추적성 (Traceability)
- [ ] source_span이 정확히 표시됨
- [ ] 원문과 추출된 요구사항의 연결이 명확함

### 5. 세분화 수준 (Granularity)
- [ ] 각 요구사항이 독립적으로 구현 가능
- [ ] 너무 크거나 작지 않은 적절한 단위
- [ ] 테스트 가능한 수준으로 작성됨

## 출력 형식

{{
  "confidence_score": 0.85,
  "quality_metrics": {{
    "completeness": 0.90,
    "clarity": 0.85,
    "consistency": 0.80,
    "traceability": 0.90,
    "granularity": 0.80
  }},
  "issues": [
    "REQ-003의 acceptance_criteria가 너무 추상적임",
    "REQ-007과 REQ-008이 유사하여 병합 검토 필요",
    "비기능 요구사항이 2개뿐으로 추가 추출 권장"
  ],
  "recommendations": [
    "성능, 보안, 가용성 요구사항을 더 세분화하세요",
    "각 요구사항에 최소 3개 이상의 acceptance_criteria 추가",
    "constraint 타입 요구사항을 별도로 분리"
  ],
  "pass": true
}}

**신뢰도 기준:**
- 0.9 이상: Excellent (그대로 사용 가능)
- 0.75~0.89: Good (경미한 수정 권장)
- 0.6~0.74: Fair (재검토 필요)
- 0.6 미만: Poor (재추출 필요)
"""

# =============================================================================
# Project Charter 생성 프롬프트
# =============================================================================

PROJECT_CHARTER_PROMPT = """
다음 정보로 프로젝트 헌장(Project Charter)을 작성하세요.

## 입력 정보
- **프로젝트명**: {{project_name}}
- **스폰서**: {{sponsor}}
- **배경**: {{background}}
- **목표**: {{objectives}}

---

# 프로젝트 헌장 (Project Charter)

## 1. 프로젝트 목적 및 정당성

### 1.1 사업 목적
[프로젝트가 해결하고자 하는 비즈니스 문제]

### 1.2 정당성
[프로젝트 수행의 타당성 및 기대 효과]

## 2. 측정 가능한 프로젝트 목표 및 관련 성공 기준

| 목표 | 성공 기준 | 측정 방법 |
|-----|----------|----------|
| 목표 1 | KPI 1 | 측정 방식 1 |
| 목표 2 | KPI 2 | 측정 방식 2 |

## 3. 상위 수준 요구사항

1. [주요 요구사항 1]
2. [주요 요구사항 2]
3. [주요 요구사항 3]

## 4. 상위 수준 프로젝트 설명, 경계 및 주요 산출물

### 4.1 프로젝트 범위
[In Scope]

### 4.2 제외 사항
[Out of Scope]

### 4.3 주요 산출물
- 산출물 1
- 산출물 2

## 5. 전체 프로젝트 리스크

| 리스크 | 영향도 | 확률 | 대응 전략 |
|-------|-------|------|----------|
| 리스크 1 | High | Medium | [대응책] |
| 리스크 2 | Medium | High | [대응책] |

## 6. 요약 마일스톤 일정

| 마일스톤 | 목표 날짜 |
|---------|----------|
| 킥오프 | [날짜] |
| 요구사항 승인 | [날짜] |
| 설계 완료 | [날짜] |
| UAT 완료 | [날짜] |
| Go-Live | [날짜] |

## 7. 요약 예산

| 항목 | 금액 |
|-----|------|
| 인건비 | [금액] |
| SW 라이선스 | [금액] |
| 인프라 | [금액] |
| **총계** | **[금액]** |

## 8. 프로젝트 승인 요구사항

### 8.1 승인 기준
- [기준 1]
- [기준 2]

### 8.2 승인자
- 프로젝트 스폰서: [이름]
- 기술 검토자: [이름]

## 9. 프로젝트 관리자, 책임 및 권한 수준

### 9.1 프로젝트 관리자
- **이름**: [PM 이름]
- **소속**: [부서/조직]

### 9.2 권한 수준
- 예산 집행 권한: [금액] 이내
- 인사 권한: 팀원 배치 및 평가
- 의사결정 권한: [범위]

## 10. 프로젝트를 후원하는 스폰서 또는 승인자

| 역할 | 이름 | 직책 | 서명 | 날짜 |
|-----|------|------|------|------|
| 프로젝트 스폰서 | {{sponsor}} | | | |
| 사업 책임자 | | | | |
| 기술 책임자 | | | | |

---

**승인일**: [날짜]
**문서 버전**: 1.0
**다음 검토일**: [날짜]
"""

# =============================================================================
# Tailoring 가이드 프롬프트
# =============================================================================

TAILORING_PROMPT = """
다음 프로젝트 특성에 맞춰 PMP 프로세스를 Tailoring하세요.

## 프로젝트 특성
- **규모**: {{size}} (소형/중형/대형)
- **방법론**: {{methodology}} (Waterfall/Agile/Hybrid)
- **복잡도**: {{complexity}} (낮음/중간/높음)
- **팀 크기**: {{team_size}}명
- **기간**: {{duration}}개월

## Tailoring 원칙

### 1. 문서화 수준

**소형 프로젝트 (팀 5명 이하, 3개월 이하):**
- 간소화된 문서 (SRS, 테스트 계획만)
- 이메일/채팅으로 의사소통

**중형 프로젝트 (팀 5-20명, 3-12개월):**
- 표준 문서 세트
- 주간 상태 보고

**대형 프로젝트 (팀 20명 이상, 12개월 이상):**
- 완전한 문서화
- 정식 변경 관리 위원회 (CCB)

### 2. 승인 프로세스

**복잡도 낮음:**
- PM 단독 승인

**복잡도 중간:**
- PM + 기술 리드 승인

**복잡도 높음:**
- PM + 기술 리드 + 스폰서 승인
- 단계별 게이트 검토

### 3. 변경 관리

**Agile:**
- 가벼운 변경 프로세스
- 스프린트 단위 조정

**Waterfall:**
- 공식 CCB 필요
- 변경 영향 분석 필수

**Hybrid:**
- 주요 변경만 CCB
- 경미한 변경은 간소화

### 4. 리스크 관리

**소형:** 주간 리스크 리뷰
**중형:** 격주 리스크 워크숍
**대형:** 주간 리스크 회의 + 월간 종합 리뷰

## 출력 JSON

{{
  "documentation": {{
    "level": "standard",
    "required_documents": [
      "요구사항 명세서 (SRS)",
      "시스템 설계서",
      "테스트 계획서",
      "운영 매뉴얼"
    ],
    "optional_documents": [
      "아키텍처 결정 기록 (ADR)",
      "성능 테스트 보고서"
    ],
    "format": "템플릿 기반, 간결한 작성"
  }},
  
  "approval_process": {{
    "gates": [
      "요구사항 승인",
      "설계 검토",
      "UAT 통과"
    ],
    "approvers": [
      "프로젝트 관리자",
      "기술 리드",
      "이해관계자 대표"
    ],
    "sla": "검토 요청 후 3영업일 이내 승인"
  }},
  
  "change_management": {{
    "process_type": "lightweight",
    "approval_threshold": "Medium 우선순위 이상",
    "ccb_required": false,
    "documentation": "변경 요청서 (간소화 양식)"
  }},
  
  "risk_management": {{
    "review_frequency": "격주",
    "risk_register_detail": "medium",
    "quantitative_analysis": false,
    "escalation_criteria": "High 리스크 발생 시 즉시 보고"
  }},
  
  "communication": {{
    "status_reports": "주간",
    "stakeholder_meetings": "격주",
    "team_standups": "일일 (Agile 적용 시)"
  }},
  
  "rationale": "중형 Agile 프로젝트로 균형잡힌 접근 필요. 문서는 필수 항목만 유지하되 품질 확보. 변경 관리는 유연하되 추적 가능하게 운영."
}}
"""