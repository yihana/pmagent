# Software Requirements Specification
**Project:** Demo Project
**Generated:** 2025-11-17T13:59:44.806165

## 1. Requirements

### REQ-001: 이메일 가입
- **Type:** functional
- **Priority:** High
- **Description:** 이메일과 비밀번호로 신규 사용자를 회원가입시킨다.
- **Source:** 문서 위치

### REQ-002: 로그인
- **Type:** functional
- **Priority:** High
- **Description:** 등록된 사용자는 이메일과 비밀번호로 로그인해야 한다.
- **Source:** 문서 위치

### REQ-003: 로그아웃
- **Type:** functional
- **Priority:** High
- **Description:** 로그인한 사용자는 세션을 종료한다.
- **Source:** 문서 위치

### REQ-004: 이메일 인증
- **Type:** functional
- **Priority:** High
- **Description:** 회원가입 시 이메일 인증을 통해 계정 활성화
- **Source:** 문서 위치

### REQ-005: 비밀번호 변경
- **Type:** functional
- **Priority:** High
- **Description:** 사용자는 현재 비밀번호로 새로운 비밀번호로 변경한다.
- **Source:** 문서 위치

### REQ-006: 비밀번호 재설정
- **Type:** functional
- **Priority:** Medium
- **Description:** 비밀번호를 잃은 사용자는 재설정 절차를 통해 비밀번호를 변경
- **Source:** 문서 위치

### REQ-007: 계정 잠금 정책
- **Type:** functional
- **Priority:** Medium
- **Description:** 연속 로그인 실패 시 계정이 잠긴다
- **Source:** 문서 위치

### REQ-008: 세션 관리
- **Type:** non-functional
- **Priority:** High
- **Description:** 세션 토큰은 서버에서 관리되고 만료 시간이 있다
- **Source:** 문서 위치

### REQ-009: 역할 생성
- **Type:** functional
- **Priority:** High
- **Description:** 역할을 생성하고 관리한다
- **Source:** 문서 위치

### REQ-010: 역할 할당
- **Type:** functional
- **Priority:** High
- **Description:** 사용자에게 역할을 할당하거나 해제한다
- **Source:** 문서 위치

### REQ-011: 권한 부여 관리
- **Type:** functional
- **Priority:** High
- **Description:** 자원별 권한 매핑을 관리한다
- **Source:** 문서 위치

### REQ-012: 자원 접근 제어 체크
- **Type:** functional
- **Priority:** High
- **Description:** 자원에 접근 시 현재 사용자의 역할/권한을 확인한다
- **Source:** 문서 위치

### REQ-013: API 응답 속도
- **Type:** non-functional
- **Priority:** High
- **Description:** API 응답은 1초 이내여야 한다.
- **Source:** 문서 위치

### REQ-014: 보안 전송
- **Type:** non-functional
- **Priority:** High
- **Description:** 데이터 전송은 TLS 1.2 이상, HTTPS를 통해 이루어진다.
- **Source:** 문서 위치

### REQ-015: 비밀번호 해시
- **Type:** non-functional
- **Priority:** High
- **Description:** 비밀번호 저장은 안전한 해시 알고리즘으로 수행한다.
- **Source:** 문서 위치

### REQ-016: 데이터베이스 제약
- **Type:** constraint
- **Priority:** High
- **Description:** 데이터베이스는 PostgreSQL을 사용한다.
- **Source:** 문서 위치

