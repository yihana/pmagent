# Software Requirements Specification
**Project:** E1-deep-0
**Generated:** 2025-11-19T00:36:04.882835

## 1. Requirements

### REQ-001: 메인 포털 구성
- **Type:** functional
- **Priority:** High
- **Description:** IT 운영 관리 시스템의 메인 페이지를 IT 포털 역할로 제공하고, 메인 배너/공지사항/콘텐츠 업로드 및 Quick Link를 지원한다.
- **Source:** 3. 프로젝트 수행 범위 - ① 메인 페이지(Main)

### REQ-002: IT SR 요청
- **Type:** functional
- **Priority:** High
- **Description:** IT SR 요청 기능을 제공하고, Knox 그룹 포탈으로 결재 상신 및 담당자 지정을 지원한다.
- **Source:** 3. 프로젝트 수행 범위 - ② IT SR (ISR)

### REQ-003: 작업 현황 업데이트
- **Type:** functional
- **Priority:** High
- **Description:** 결재 이후 작업 현황이 업데이트되고 관련자에게 이메일로 공유된다.
- **Source:** 3. 프로젝트 수행 범위 - ② IT SR (ISR)

### REQ-004: 자산 등록 및 관리
- **Type:** functional
- **Priority:** High
- **Description:** IT Asset(AMS)에서 구매·개발 완료 자산의 소유자와 위치를 포함해 자산을 등록·관리한다.
- **Source:** 3. 프로젝트 수행 범위 - ③ IT Asset (AMS)

### REQ-005: AMS-SR 연동 조회
- **Type:** functional
- **Priority:** Medium
- **Description:** IT SR 요청 기반 구입인 경우 품의(CMS)와 SR(ISR) 내용을 연동 조회한다.
- **Source:** 3. 프로젝트 수행 범위 - ③ IT Asset (AMS)

### REQ-006: 연간 예산 관리
- **Type:** functional
- **Priority:** High
- **Description:** IT Budget(BMS)에서 매년 9월에 예산 신청/등록/조회하고, 예산 변동 시 기록 관리한다.
- **Source:** 3. 프로젝트 수행 범위 - ④ IT Budget (BMS)

### REQ-007: 예산 Excel 업로드
- **Type:** functional
- **Priority:** Medium
- **Description:** 예산 등록 시 Excel 일괄 업로드를 지원한다.
- **Source:** 3. 프로젝트 수행 범위 - ④ IT Budget (BMS)

### REQ-008: CMS Knox API 연동
- **Type:** functional
- **Priority:** High
- **Description:** Knox 포탈 API 연동 결재 및 품의 관리, 비용 산정 기반 지급/정산 데이터를 생성한다.
- **Source:** 3. 프로젝트 수행 범위 - ⑤ IT Contract & Approval (CMS)

### REQ-009: 지급/정산 데이터 흐름
- **Type:** functional
- **Priority:** High
- **Description:** 실시품의 시 비용 및 지급 횟수 기반 지급 데이터 생성 및 정산 가능하도록 구성한다.
- **Source:** 3. 프로젝트 수행 범위 - ⑤ IT Contract & Approval (CMS)

### REQ-010: IPS 프로젝트 관리
- **Type:** functional
- **Priority:** High
- **Description:** 프로젝트 유관자 등록, 진행사항/요청사항 기록, 외주 인력 등록 등 태그 관리, 방화벽/서비스 인스턴스/라이선스/계정 등의 정보를 기록하고, 종료 시 보안 검수 및 유지보수 여부를 기록한다.
- **Source:** 3. 프로젝트 수행 범위 - ⑥ IT Project (IPS)

### REQ-011: 데이터 변경 이력 조회
- **Type:** non-functional
- **Priority:** High
- **Description:** 시스템 전체 데이터 변경 이력을 조회하고 Excel로 다운로드 가능하게 한다.
- **Source:** 3. 공통 사항

### REQ-012: 보안 검수 절차
- **Type:** non-functional
- **Priority:** High
- **Description:** 프로젝트 IPS의 종료 시 보안 검수를 수행하고 완료 품의를 생성한다.
- **Source:** 3. 프로젝트 수행 범위 - ⑥ IT Project (IPS)

### REQ-013: 유지보수 관리
- **Type:** functional
- **Priority:** Medium
- **Description:** 종료 후 유지보수 여부를 기록하고 연 단위 유지보수 계약 판단을 한다.
- **Source:** 3. 프로젝트 수행 범위 - ⑥ IT Project (IPS)

### REQ-014: 시스템 환경 제약
- **Type:** constraint
- **Priority:** High
- **Description:** DBMS는 Oracle DB를 사용하고, Web Server는 Apache/Tomcat(.NET Core 중 선택), OS는 Windows 또는 Linux로 구성하며 하드웨어 사양은 4코어/16GB/1TB를 기준으로 한다.
- **Source:** 4. 시스템 개요

### REQ-015: 배포 환경 협의
- **Type:** constraint
- **Priority:** Medium
- **Description:** 개발착수 후 개발계–검증계–운영계 배포 환경 협의가 진행되어야 한다(환경 구성 확정).
- **Source:** 4. 시스템 개요

