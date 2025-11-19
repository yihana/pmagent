# Software Requirements Specification
**Project:** E4-1
**Generated:** 2025-11-19T00:49:41.934354

## 1. Requirements

### REQ-001: 전산장비 24시간
- **Type:** non-functional
- **Priority:** High
- **Description:** 전산장비는 휴일·야간을 포함한 24시간 운영 및 대응 체계를 갖춘다.
- **Source:** MSR-001

### REQ-002: 정기 점검/패치
- **Type:** non-functional
- **Priority:** High
- **Description:** 매월 1회 이상 정기 점검 및 패치 적용을 수행한다.
- **Source:** MSR-001

### REQ-003: 장애대응 시간
- **Type:** functional
- **Priority:** High
- **Description:** 장애 발생 시 현장 도착 2시간 이내, 4시간 내 복구를 목표로 한다.
- **Source:** MSR-001

### REQ-004: 대체장비 제공
- **Type:** functional
- **Priority:** Medium
- **Description:** 복구 불가 시 대체장비를 제공한다.
- **Source:** MSR-001

### REQ-005: 부품 교체정책
- **Type:** functional
- **Priority:** Medium
- **Description:** 충분한 부품을 확보하고 필요 시 무상 교체를 한다.
- **Source:** MSR-001

### REQ-006: 보고 체계 운영
- **Type:** functional
- **Priority:** Medium
- **Description:** 주간/월간/작업/장애처리/위험관리 보고서를 정기적으로 제출한다.
- **Source:** MSR-001

### REQ-007: 네트워크 구성 무상 지원
- **Type:** constraint
- **Priority:** Medium
- **Description:** 사무실 조정/이전 시 네트워크 구성 무상 지원한다.
- **Source:** MSR-002

### REQ-008: 연동 점검 포함
- **Type:** functional
- **Priority:** Medium
- **Description:** 정보보호 시스템 연동 점검을 포함한다.
- **Source:** MSR-002

### REQ-009: 분기 방문 규정
- **Type:** constraint
- **Priority:** Medium
- **Description:** 고흥항공센터는 분기별 현장 방문을 이행한다.
- **Source:** MSR-002

### REQ-010: 장애 즉시 점검
- **Type:** functional
- **Priority:** High
- **Description:** 장애 발생 시 즉시 통합 점검을 수행한다.
- **Source:** MSR-002

### REQ-011: 패키지 SW 업데이트 관리
- **Type:** functional
- **Priority:** Medium
- **Description:** 패키지 SW 업데이트 및 패치 관리 체계를 운영한다.
- **Source:** MSR-003

### REQ-012: 관리자 교육
- **Type:** functional
- **Priority:** Medium
- **Description:** 패키지 SW 관리자 교육을 제공한다.
- **Source:** MSR-003

### REQ-013: PC OS 설치/패치
- **Type:** functional
- **Priority:** Medium
- **Description:** PC 사용자에 대한 OS 설치/설정/패치를 수행한다.
- **Source:** MSR-004

### REQ-014: OA 소프트웨어 설치/관리
- **Type:** functional
- **Priority:** Medium
- **Description:** OA 소프트웨어의 설치 및 관리 업무를 수행한다.
- **Source:** MSR-004

### REQ-015: AD 계정 관리
- **Type:** functional
- **Priority:** High
- **Description:** AD 계정의 생성/삭제 및 비밀번호 관리를 수행한다.
- **Source:** MSR-004

### REQ-016: 프린터 지원
- **Type:** functional
- **Priority:** Low
- **Description:** 프린터/복합기 지원을 제공한다.
- **Source:** MSR-004

### REQ-017: VPN/클라우드 지원
- **Type:** functional
- **Priority:** High
- **Description:** VPN 신청 및 계정 관리와 클라우드 스토리지 지원을 제공한다.
- **Source:** MSR-004

### REQ-018: 보안 USB 안내
- **Type:** functional
- **Priority:** Medium
- **Description:** 보안 USB 설치 및 이용 안내를 제공한다.
- **Source:** SER-004

### REQ-019: 소프트웨어 라이선스 관리
- **Type:** functional
- **Priority:** Medium
- **Description:** 소프트웨어 라이선스를 관리한다.
- **Source:** SER-004

### REQ-020: 망연계 계정 초기화
- **Type:** functional
- **Priority:** Medium
- **Description:** 망연계 계정의 비밀번호 초기화를 관리한다.
- **Source:** SER-005

### REQ-021: 운영시간 관리
- **Type:** constraint
- **Priority:** High
- **Description:** IT 헬프데스크 운영시간은 평일 08:30~18:00이다.
- **Source:** MSR-005

### REQ-022: 상주 인력 고용기준
- **Type:** constraint
- **Priority:** High
- **Description:** 상주 인력은 공고 이전에 고용된 소속직원으로 한정한다.
- **Source:** MHR-001

### REQ-023: 근무시간·초과근무
- **Type:** functional
- **Priority:** Medium
- **Description:** 근무시간은 9:00~18:00이며 필요 시 조기출근/야간/휴일근무를 수행한다.
- **Source:** MHR-001

### REQ-024: 휴가시 대체인력
- **Type:** constraint
- **Priority:** Medium
- **Description:** 휴가로 2일 이상 공백 시 대체 인력을 투입한다.
- **Source:** MHR-001

### REQ-025: 인력 교체 원칙
- **Type:** constraint
- **Priority:** Medium
- **Description:** 원칙적으로 인력 교체는 불가하며 필요 시 연구원 승인 절차를 따른다.
- **Source:** MHR-001

### REQ-026: 해지 후 인계 의무
- **Type:** constraint
- **Priority:** High
- **Description:** 계약 해지 시 인계 의무를 이행해야 한다.
- **Source:** RER-002

### REQ-027: 장애지연 벌칙
- **Type:** constraint
- **Priority:** High
- **Description:** 장애지연 시 벌칙금을 부과한다.
- **Source:** RER-003

### REQ-028: 정기점검 미이행 제재
- **Type:** constraint
- **Priority:** Medium
- **Description:** 정기점검 미이행 시 유지보수료를 감액한다.
- **Source:** RER-003

### REQ-029: EA 현행화 산출물
- **Type:** functional
- **Priority:** Medium
- **Description:** EA 현행화 산출물을 제출한다.
- **Source:** PMR-001

### REQ-030: EA 포털 등록 지원
- **Type:** functional
- **Priority:** Medium
- **Description:** 범정부 EA포털 등록을 지원한다.
- **Source:** PMR-001

### REQ-031: 변경 시 현행화 자료 제출
- **Type:** functional
- **Priority:** Medium
- **Description:** 변경 발생 시 현행화 자료를 추가 제출한다.
- **Source:** PMR-001

### REQ-032: MS Premier Support 50시간
- **Type:** functional
- **Priority:** High
- **Description:** MS Premier Support를 50시간 이상 제공한다.
- **Source:** PSR-001

### REQ-033: Microsoft/Nutanix 교육
- **Type:** functional
- **Priority:** Medium
- **Description:** Microsoft/Nutanix 교육을 지원한다.
- **Source:** PSR-001

### REQ-034: 운영자 교육/온사이트
- **Type:** functional
- **Priority:** Medium
- **Description:** 운영자 교육 및 On-Site 기술 지원을 제공한다.
- **Source:** PSR-001

### REQ-035: 장애조치 매뉴얼
- **Type:** functional
- **Priority:** Medium
- **Description:** 장애 조치 매뉴얼을 제공한다.
- **Source:** PSR-001

### REQ-036: 운영매뉴얼 제공
- **Type:** functional
- **Priority:** Medium
- **Description:** 운영매뉴얼을 제공한다.
- **Source:** PSR-001

