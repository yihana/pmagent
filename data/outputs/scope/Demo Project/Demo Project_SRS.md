# Software Requirements Specification
**Project:** Demo Project
**Generated:** 2025-11-16T05:25:07.125880

## 1. Requirements

### REQ-001: 메인배너 관리
- **Type:** functional
- **Priority:** High
- **Description:** 메인 페이지에 배너를 관리할 수 있어야 한다. 배너는 제목, 링크, 시작일/종료일, 노출 여부를 포함한다.
- **Source:** 제안요청서 > 3. 프로젝트 수행 범위

### REQ-002: 공지사항 관리
- **Type:** functional
- **Priority:** High
- **Description:** 공지사항을 생성, 수정, 삭제하는 기능을 제공하고 메인에 노출 여부를 제어할 수 있어야 한다.
- **Source:** 제안요청서 > 3. 프로젝트 수행 범위

### REQ-003: IT콘텐츠 업로드
- **Type:** functional
- **Priority:** High
- **Description:** IT 콘텐츠를 업로드하고 메타데이터와 함께 관리할 수 있어야 한다.
- **Source:** 제안요청서 > 3. 프로젝트 수행 범위

### REQ-004: QuickLink 관리
- **Type:** functional
- **Priority:** High
- **Description:** 전사 포털의 Quick Link를 관리하고, 화면에 반영되도록 해야 한다.
- **Source:** 제안요청서 > 3. 프로젝트 수행 범위

### REQ-005: SR 상신 결재
- **Type:** functional
- **Priority:** High
- **Description:** IT SR 요청 기능을 상신하고 Knox 그룹 포탈으로 결재를 진행해야 한다.
- **Source:** 제안요청서 > 3. 프로젝트 수행 범위

### REQ-006: SR 현황 공유
- **Type:** functional
- **Priority:** Medium
- **Description:** SR 처리 현황을 담당자 지정 및 이메일로 공유할 수 있어야 한다.
- **Source:** 제안요청서 > 3. 프로젝트 수행 범위

### REQ-007: IT자산 등록 관리
- **Type:** functional
- **Priority:** High
- **Description:** 구매·개발 완료 자산을 등록하고 소유자/위치를 지정해 관리해야 한다.
- **Source:** 제안요청서 > 3. 프로젝트 수행 범위

### REQ-008: SR/구매 이력 조회
- **Type:** functional
- **Priority:** Medium
- **Description:** SR 신청 시 구입일, 이력 등을 조회할 수 있는 화면을 제공해야 한다.
- **Source:** 제안요청서 > 3. 프로젝트 수행 범위

### REQ-009: 예산 9월 신청
- **Type:** functional
- **Priority:** High
- **Description:** 내년 예산(개발/비용)을 매년 9월에 신청, 등록, 조회할 수 있어야 한다.
- **Source:** 제안요청서 > 3. 프로젝트 수행 범위

### REQ-010: 예산 Excel 등록
- **Type:** functional
- **Priority:** Medium
- **Description:** 예산(개발/비용) Excel 파일을 이용한 대량 등록이 가능해야 한다.
- **Source:** 제안요청서 > 3. 프로젝트 수행 범위

### REQ-011: 계약 품의 관리
- **Type:** functional
- **Priority:** High
- **Description:** 계약, 실시, 정산, 지급, 수정 품의를 작성하고 조회해야 한다.
- **Source:** 제안요청서 > 3. 프로젝트 수행 범위

### REQ-012: 지급 관리
- **Type:** functional
- **Priority:** Medium
- **Description:** 지급 데이터 저장 및 지급 횟수 관리 등 지급 관련 품의를 처리해야 한다.
- **Source:** 제안요청서 > 3. 프로젝트 수행 범위

### REQ-013:  Knox 결재 연동
- **Type:** functional
- **Priority:** Medium
- **Description:** 계약/품의 상신 시 Knox 그룹 포탈 API를 이용한 결재 연동이 필요하다.
- **Source:** 제안요청서 > 3. 프로젝트 수행 범위

### REQ-014: IPS 프로젝트 관리
- **Type:** functional
- **Priority:** High
- **Description:** 프로젝트 유관자 등록, ISR의 요청사항 관리, 방화벽/서비스 인스턴스/라이선스/계정 정보 기록을 관리해야 한다.
- **Source:** 제안요청서 > 3. 프로젝트 수행 범위

### REQ-015: 유지보수 여부 관리
- **Type:** functional
- **Priority:** Medium
- **Description:** 프로젝트 종료 후 유지/보수 여부를 매년 확인하고 관리해야 한다.
- **Source:** 제안요청서 > 3. 프로젝트 수행 범위

### REQ-016: 데이터 변경 이력
- **Type:** functional
- **Priority:** Medium
- **Description:** 데이터 변경 내역을 확인하고 엑셀로 다운로드할 수 있어야 한다.
- **Source:** 제안요청서 > 3. 프로젝트 수행 범위

### REQ-017: 시스템 가용성
- **Type:** non-functional
- **Priority:** High
- **Description:** 시스템은 99.9% 가용성을 목표로 운영되어야 한다.
- **Source:** 제안요청서 > 4. 시스템 개요

### REQ-018: 응답 속도
- **Type:** non-functional
- **Priority:** High
- **Description:** 웹 서비스와 API 응답은 1초 이내로 처리되어야 한다.
- **Source:** 제안요청서 > 4. 시스템 개요

### REQ-019: 데이터베이스 제약
- **Type:** constraint
- **Priority:** High
- **Description:** 데이터베이스는 Oracle DB를 사용해야 한다.
- **Source:** Table 1

### REQ-020: OS 배포 제약
- **Type:** constraint
- **Priority:** High
- **Description:** 배포 대상 OS는 Windows 또는 Linux 중 하나로 결정하여 운영한다.
- **Source:** Table 1

### REQ-021: 개발언어 제약
- **Type:** constraint
- **Priority:** High
- **Description:** 개발 언어는 Java 또는 C# 중 하나를 선택해 프로젝트를 구현한다.
- **Source:** Table 1

### REQ-022: 웹서버 제약
- **Type:** constraint
- **Priority:** Medium
- **Description:** 웹 서버 구성은 Apache/Tomcat 조합 또는 .NET Core 중 하나로 배포한다.
- **Source:** Table 1

