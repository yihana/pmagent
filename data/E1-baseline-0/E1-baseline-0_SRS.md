# Software Requirements Specification
**Project:** E1-baseline-0
**Generated:** 2025-11-19T02:22:34.772991

## 1. Requirements

### REQ-001: 메인 포털 구현
- **Type:** functional
- **Priority:** High
- **Description:** IT 운영 관리 시스템의 메인 페이지를 구현하고 배너/공지사항/IT 콘텐츠 업로드 및 Quick Link를 제공한다.
- **Source:** 문서 3. 프로젝트 수행 범위 - ① 메인 페이지(Main)

### REQ-002: IT SR 요청 기능
- **Type:** functional
- **Priority:** High
- **Description:** IT SR 요청을 생성·조회하고 상태를 관리할 수 있어야 한다.
- **Source:** 문서 3. 프로젝트 수행 범위 - ② IT SR (ISR)

### REQ-003: Knox 결재 상신
- **Type:** functional
- **Priority:** Medium
- **Description:** SR 결재를 Knox 포탈 API를 통해 상신하고 결재 상태를 시스템에 반영해야 한다.
- **Source:** 문서 3. 프로젝트 수행 범위 - ② IT SR (ISR)

### REQ-004: SR 승인 후 담당자 지정
- **Type:** functional
- **Priority:** Medium
- **Description:** SR 결재 승인 후 해당 작업의 담당자를 자동으로 지정하고 알림을 전송한다.
- **Source:** 문서 3. 프로젝트 수행 범위 - ② IT SR (ISR)

### REQ-005: IT Asset 등록/관리
- **Type:** functional
- **Priority:** Medium
- **Description:** 자산의 등록/수정/삭제 및 소유자와 위치 정보 관리 기능을 제공한다.
- **Source:** 문서 3. 프로젝트 수행 범위 - ③ IT Asset (AMS)

### REQ-006: 자산-SR 연동 조회
- **Type:** functional
- **Priority:** Medium
- **Description:** 자산과 SR 간의 관련 이력(구매 시 품의(CMS) 및 SR(ISR) 연계)을 조회할 수 있다.
- **Source:** 문서 3. 프로젝트 수행 범위 - ③ IT Asset (AMS)

### REQ-007: IT Budget 연간 예산
- **Type:** functional
- **Priority:** High
- **Description:** 매년 9월에 정기 예산(개발/비용) 신청·등록·조회 기능을 제공한다.
- **Source:** 문서 3. 프로젝트 수행 범위 - ④ IT Budget (BMS)

### REQ-008: Budget 변경 이력 관리
- **Type:** functional
- **Priority:** Medium
- **Description:** 예산 변경 이력을 저장하고 조회할 수 있어야 한다.
- **Source:** 문서 3. 프로젝트 수행 범위 - ④ IT Budget (BMS)

### REQ-009: CMS 승인 금액 자동 반영
- **Type:** functional
- **Priority:** Medium
- **Description:** CMS 승인 금액 및 관련 금액(승인잔액/지급금액/지급잔액)이 예산 화면에 자동으로 반영되어야 한다.
- **Source:** 문서 3. 프로젝트 수행 범위 - ④ IT Budget (BMS)

### REQ-010: IT Contract & Approval 관리
- **Type:** functional
- **Priority:** High
- **Description:** 계약/실시/정산/지급/수정 품의 작성 및 조회와 보고서 작성/결재를 지원한다.
- **Source:** 문서 3. 프로젝트 수행 범위 - ⑤ IT Contract & Approval (CMS)

### REQ-011: IPS 프로젝트 관리
- **Type:** functional
- **Priority:** Medium
- **Description:** 프로젝트 유관자 등록, 진행사항/요청사항 기록 및 ISR의 외주 인력/PC 세팅 등 요청 관리 태그를 관리한다.
- **Source:** 문서 3. 프로젝트 수행 범위 - ⑥ IT Project (IPS)

### REQ-012: 프로젝트 종료 및 보안/유지보수
- **Type:** functional
- **Priority:** Medium
- **Description:** 프로젝트 완료 후 보안 검수 및 완료 품의를 생성하고 종료 후 유지보수 여부를 기록한다.
- **Source:** 문서 3. 프로젝트 수행 범위 - ⑥ IT Project (IPS)

### REQ-013: 데이터 변경 내역/엑셀
- **Type:** functional
- **Priority:** Medium
- **Description:** 데이터 변경 내역 조회 및 Excel 다운로드를 지원한다.
- **Source:** 문서 3. 공통 사항

### REQ-014: 시스템 제약
- **Type:** constraint
- **Priority:** High
- **Description:** 시스템 구축 시 다음 제약사항을 준수해야 한다: Oracle DB, Web Server: Apache/Tomcat/.NET Core, Language: Java/C#, OS: Windows 또는 Linux, HW: 4코어 CPU/16GB RAM/1TB HDD.
- **Source:** 문서 4. 시스템 개요

