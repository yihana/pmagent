# Software Requirements Specification
**Project:** E4-0
**Generated:** 2025-11-19T00:48:28.106687

## 1. Requirements

### REQ-001: IT 포털 메인
- **Type:** functional
- **Priority:** High
- **Description:** 메인 페이지가 IT 운영 관리 시스템의 포털 역할을 수행해야 하며, 메인 배너, 공지사항, IT 콘텐츠 업로드 기능을 제공하고 각 IT 프로세스로 가는 Quick Link를 제공한다.
- **Source:** 3. 프로젝트 수행 범위 > ① 메인 페이지(Main)

### REQ-002: IT SR 요청 기능
- **Type:** functional
- **Priority:** High
- **Description:** IT SR 요청을 생성하고 결재 상신 후 담당자를 지정하며, 작업 현황 업데이트 및 관련 알림이 전송되도록 해야 한다.
- **Source:** 3. 프로젝트 수행 범위 > ② IT SR (ISR)

### REQ-003: IT Asset 관리
- **Type:** functional
- **Priority:** High
- **Description:** 구매·개발 완료 자산을 등록하고 소유자와 위치 정보를 관리하며, IT SR 신청 기반 구입 시 품의(CMS)와 SR(ISR) 내용을 연동 조회할 수 있어야 한다.
- **Source:** 3. 프로젝트 수행 범위 > ③ IT Asset (AMS)

### REQ-004: IT Budget 관리
- **Type:** functional
- **Priority:** High
- **Description:** 매년 9월 정기 예산을 신청/등록/조회하고, 예산 변동을 기록하며, 비용 예산을 Excel 일괄 업로드할 수 있어야 한다. 품의 승인 정보 기반으로 금액이 자동 반영되고 사용 내역도 기록한다.
- **Source:** 3. 프로젝트 수행 범위 > ④ IT Budget (BMS)

### REQ-005: IT Contract & Approval
- **Type:** functional
- **Priority:** High
- **Description:** 계약/실시/정산/지급/수정 품의에 대한 보고서 작성, 결재 조회를 지원하며, 필요 시 지급 횟수 기반으로 지급 데이터를 생성한다.
- **Source:** 3. 프로젝트 수행 범위 > ⑤ IT Contract & Approval (CMS)

### REQ-006: IT Project 관리
- **Type:** functional
- **Priority:** High
- **Description:** 프로젝트 유관자를 등록하고 프로젝트 진행사항 및 요청사항을 기록하며, ISR의 외주 인력 등록·PC 세팅 등의 요청을 태그로 관리한다. 관련 정보(방화벽/서비스 인스턴스/라이선스/계정 등) 기록, 프로젝트 완료 시 보안 검수 및 완료 품의, 종료 후 유지보수 여부를 기록한다.
- **Source:** 3. 프로젝트 수행 범위 > ⑥ IT Project (IPS)

### REQ-007: 데이터 이력/다운로드
- **Type:** functional
- **Priority:** Medium
- **Description:** 시스템 데이터 변경 내역 조회 및 Excel 다운로드 기능을 제공해야 한다.
- **Source:** 3. 프로젝트 수행 범위 > 공통 사항

### REQ-008: 데이터베이스 제약
- **Type:** constraint
- **Priority:** High
- **Description:** 데이터베이스는 Oracle DB를 사용해야 한다.
- **Source:** 5. 시스템 개요

### REQ-009: 웹 서버 구성 제약
- **Type:** constraint
- **Priority:** High
- **Description:** 웹 서버 구성은 Apache, Tomcat(미정), .NET Core(미정) 중 하나 이상으로 구성될 예정이며 상세 구성은 개발착수 후 결정된다.
- **Source:** 5. 시스템 개요

### REQ-010: 운영 체제 제약
- **Type:** constraint
- **Priority:** High
- **Description:** 운영 체제(OS)는 Windows 또는 Linux 중 하나로 구성되며 상세 구성은 개발 착수 시 확정된다.
- **Source:** 5. 시스템 개요

### REQ-011: 하드웨어 사양
- **Type:** constraint
- **Priority:** Medium
- **Description:** 시스템 하드웨어는 CPU 4코어, RAM 16GB, HDD 1TB의 기본 사양을 충족해야 한다.
- **Source:** 4. 시스템 개요

### REQ-012: Knox API 결재 연동
- **Type:** functional
- **Priority:** High
- **Description:** CK Knox 포탈 API를 이용한 결재 상신/조회 연동을 구현한다.
- **Source:** 3. IT Contract & Approval (CMS) – Knox 포탈 API 연동

