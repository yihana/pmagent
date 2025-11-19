# Software Requirements Specification
**Project:** E1-baseline-1
**Generated:** 2025-11-19T00:37:23.014578

## 1. Requirements

### REQ-001: 24시간 운영 체계
- **Type:** non-functional
- **Priority:** High
- **Description:** 전산장비 유지보수는 24시간 운영되며 휴일/야간에도 무관하게 대응해야 한다.
- **Source:** 2. 가. MSR-001

### REQ-002: 현장출동 2시간 이내
- **Type:** functional
- **Priority:** High
- **Description:** 장애 발생 시 현장 방문은 2시간 이내에 이뤄져야 한다.
- **Source:** 2. 가. MSR-001

### REQ-003: 장애 복구 4시간 이내
- **Type:** functional
- **Priority:** High
- **Description:** 장애 발생 시 복구는 4시간 이내에 완료되어야 한다.
- **Source:** 2. 가. MSR-001

### REQ-004: 대체장비 제공
- **Type:** functional
- **Priority:** High
- **Description:** 복구 불가 시 대체장비를 즉시 제공해야 한다.
- **Source:** 2. 가. MSR-001

### REQ-005: 장애보고서 제출 48시간
- **Type:** functional
- **Priority:** High
- **Description:** 장애 발생 후 48시간 이내에 장애보고서를 제출해야 한다.
- **Source:** 2. 가. MSR-001

### REQ-006: 월간 점검 및 패치 적용
- **Type:** functional
- **Priority:** High
- **Description:** 매월 1회 이상 점검 및 패치를 적용한다.
- **Source:** 2. 가. MSR-001

### REQ-007: 주간 보고 운영
- **Type:** functional
- **Priority:** Medium
- **Description:** 주간보고서를 주간 단위로 작성·제출한다.
- **Source:** 2. 가. MSR-001

### REQ-008: 월간 보고 운영
- **Type:** functional
- **Priority:** Medium
- **Description:** 월간보고서를 매월 말까지 제출한다.
- **Source:** 2. 가. MSR-001

### REQ-009: 작업보고 운영
- **Type:** functional
- **Priority:** Medium
- **Description:** 작업 수행 내용은 작업보고서로 기록·제출한다.
- **Source:** 2. 가. MSR-001

### REQ-010: 장애처리 보고 운영
- **Type:** functional
- **Priority:** Medium
- **Description:** 장애처리 보고서는 장애 종료 후 제출한다.
- **Source:** 2. 가. MSR-001

### REQ-011: 위험관리 보고 운영
- **Type:** functional
- **Priority:** Medium
- **Description:** 위험관리 보고서를 주기적으로 제출한다.
- **Source:** 2. 가. MSR-001

### REQ-012: HW/SW 업데이트 교체 지원
- **Type:** functional
- **Priority:** Medium
- **Description:** HW/SW 업데이트 및 교체를 지원한다.
- **Source:** MSR-001

### REQ-013: 부품 확보 및 무상교체
- **Type:** functional
- **Priority:** Medium
- **Description:** 충분한 부품 재고를 확보하고 무상으로 교체한다.
- **Source:** MSR-001

### REQ-014: 네트워크 무상 구성 지원
- **Type:** functional
- **Priority:** High
- **Description:** 사무실 이전 시 네트워크 구성은 무상으로 지원한다.
- **Source:** MSR-002

### REQ-015: 정보보호 연동점검 포함
- **Type:** functional
- **Priority:** High
- **Description:** 정보보호 시스템 연동 점검을 포함한 네트워크 점검을 수행한다.
- **Source:** MSR-002

### REQ-016: 고흥센터 분기 방문
- **Type:** functional
- **Priority:** Medium
- **Description:** 고흥센터는 분기별 현장 방문이 필수다.
- **Source:** MSR-002

### REQ-017: 장애 즉시 통합점검
- **Type:** functional
- **Priority:** High
- **Description:** 장애 발생 시 즉시 통합 점검을 수행한다.
- **Source:** MSR-002

### REQ-018: 월 1회 원격점검
- **Type:** functional
- **Priority:** Medium
- **Description:** 월 1회 원격 점검을 수행한다.
- **Source:** MSR-003

### REQ-019: 분기 방문 점검
- **Type:** functional
- **Priority:** Medium
- **Description:** 패키지 SW의 분기 방문 점검을 수행한다.
- **Source:** MSR-003

### REQ-020: 패키지 SW 업데이트/패치
- **Type:** functional
- **Priority:** High
- **Description:** 패키지 SW의 업데이트 및 패치를 정기적으로 수행한다.
- **Source:** MSR-003

### REQ-021: 관리자 교육
- **Type:** functional
- **Priority:** Medium
- **Description:** 관리자 대상 교육을 제공한다.
- **Source:** MSR-003

### REQ-022: 원격 점검 기록
- **Type:** non-functional
- **Priority:** Medium
- **Description:** 월 1회 원격 점검의 기록 관리가 필요하다.
- **Source:** MSR-003

### REQ-023: OS 설치/패치 지원
- **Type:** functional
- **Priority:** Medium
- **Description:** PC 이용자에 대한 OS 설치/설정/패치를 지원한다.
- **Source:** MSR-004

### REQ-024: OA 소프트웨어 관리
- **Type:** functional
- **Priority:** Medium
- **Description:** OA 소프트웨어를 관리한다.
- **Source:** MSR-004

### REQ-025: AD 계정 관리
- **Type:** functional
- **Priority:** High
- **Description:** AD 계정의 생성/삭제를 관리한다.
- **Source:** MSR-004

### REQ-026: 프린터/복합기 관리
- **Type:** functional
- **Priority:** Low
- **Description:** 프린터 및 복합기의 관리 및 지원을 수행한다.
- **Source:** MSR-004

### REQ-027: 네트워크 설정/케이블 제작
- **Type:** functional
- **Priority:** Medium
- **Description:** 네트워크 설정 및 케이블 제작을 지원한다.
- **Source:** MSR-004

### REQ-028: VPN/클라우드 스토리지
- **Type:** functional
- **Priority:** Medium
- **Description:** VPN 및 클라우드 스토리지를 관리한다.
- **Source:** MSR-004

### REQ-029: 바이러스 치료
- **Type:** functional
- **Priority:** Medium
- **Description:** 바이러스 치료 및 악성코드 제거를 수행한다.
- **Source:** MSR-004

### REQ-030: 부품 교체 비용처리
- **Type:** functional
- **Priority:** Medium
- **Description:** 고장 부품의 실비 교체를 처리한다.
- **Source:** MSR-004

### REQ-031: 장애 8시간 이내 처리
- **Type:** functional
- **Priority:** Medium
- **Description:** 장애 처리는 8시간 이내에 원칙적으로 해결한다.
- **Source:** MSR-004

### REQ-032: IT 헬프데스크 운영
- **Type:** functional
- **Priority:** High
- **Description:** 티켓 접수 및 분류를 통해 헬프데스크를 운영한다.
- **Source:** MSR-005

### REQ-033: IP/NAC 인증 관리
- **Type:** functional
- **Priority:** High
- **Description:** IP/NAC 인증 관리를 수행한다.
- **Source:** MSR-005

### REQ-034: AD 계정 생성/삭제
- **Type:** functional
- **Priority:** High
- **Description:** AD 계정의 생성 및 삭제를 관리한다.
- **Source:** MSR-005

### REQ-035: 메일/그룹 관리
- **Type:** functional
- **Priority:** Medium
- **Description:** 메일 계정 및 그룹 관리를 수행한다.
- **Source:** MSR-005

### REQ-036: VPN 신청 및 계정관리
- **Type:** functional
- **Priority:** Medium
- **Description:** VPN 신청 및 계정 관리를 수행한다.
- **Source:** MSR-005

### REQ-037: 보안USB 설치 안내
- **Type:** functional
- **Priority:** Low
- **Description:** 보안USB 설치 및 이용에 대해 안내한다.
- **Source:** MSR-005

### REQ-038: 소프트웨어 라이선스 관리
- **Type:** functional
- **Priority:** High
- **Description:** 소프트웨어 라이선스를 관리한다.
- **Source:** MSR-005

### REQ-039: 망연계 계정 초기화
- **Type:** functional
- **Priority:** Medium
- **Description:** 망연계 계정의 비밀번호 초기화를 관리한다.
- **Source:** MSR-005

### REQ-040: 운영시간 관리
- **Type:** non-functional
- **Priority:** Medium
- **Description:** IT 헬프데스크 운영시간은 08:30~18:00이다.
- **Source:** MSR-005

### REQ-041: 보안 사고 처리 지원
- **Type:** functional
- **Priority:** High
- **Description:** 보안 사고 시 대응을 지원한다.
- **Source:** SER-001

### REQ-042: 월간 보안점검
- **Type:** non-functional
- **Priority:** High
- **Description:** 월 1회 보안점검을 수행한다.
- **Source:** SER-002

### REQ-043: 개인정보보호 진단 지원
- **Type:** functional
- **Priority:** High
- **Description:** 개인정보보호 진단을 지원한다.
- **Source:** SER-003

### REQ-044: 상주 인력 근무시간
- **Type:** constraint
- **Priority:** High
- **Description:** 상주 인력은 9:00~18:00에 근무한다.
- **Source:** MHR-001

