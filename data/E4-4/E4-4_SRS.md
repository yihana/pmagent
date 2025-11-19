# Software Requirements Specification
**Project:** E4-4
**Generated:** 2025-11-19T00:52:14.984641

## 1. Requirements

### REQ-001: 대상 기업 수 제약
- **Type:** constraint
- **Priority:** High
- **Description:** 대상 기업은 KOSPI 및 KOSDAQ100 구성원으로 한정되며, 총 수는 약 1,000개로 정의한다.
- **Source:** Ⅰ. 선정 개요 > 1 ESG 평가데이터 > 1.1 평가대상

### REQ-002: 원점수/산출근거 제공
- **Type:** functional
- **Priority:** High
- **Description:** ESG 평가 데이터에 원점수와 산출근거를 포함하고, 이슈별 점수와 종합 등급·순위를 함께 제공한다.
- **Source:** 1. ESG 평가데이터 > 1.3 제공내역

### REQ-003: 이슈별 점수 제공
- **Type:** functional
- **Priority:** High
- **Description:** 각 ESG 이슈에 대해 점수를 부여하고, 이슈별 점수 체계가 문서에 명시되어 있어야 한다.
- **Source:** 1. ESG 평가데이터 > 1.3 제공내역

### REQ-004: 종합 등급/순위 제공
- **Type:** functional
- **Priority:** High
- **Description:** ESG 종합 등급과 순위를 기업별로 제공한다.
- **Source:** 1. ESG 평가데이터 > 1.3 제공내역

### REQ-005: 연 2회 제공 일정
- **Type:** constraint
- **Priority:** High
- **Description:** ESG 평가 데이터는 연 2회(6월, 11월) 정기적으로 제공되어야 한다.
- **Source:** Ⅰ. 선정 개요 > 사업기간 및 제공주기

### REQ-006: 기업별 ESG 분석 보고서 제공
- **Type:** functional
- **Priority:** Medium
- **Description:** ESG 이슈 리서치의 기업별 ESG 분석 보고서를 제공한다.
- **Source:** Ⅱ. ESG 이슈 리서치 > 제공내역

### REQ-007: 컨트러버시 분석 보고서 제공
- **Type:** functional
- **Priority:** Medium
- **Description:** ESG 이슈 리서치의 컨트러버시(이슈) 분석 보고서를 제공한다.
- **Source:** Ⅱ. ESG 이슈 리서치 > 컨트러버시 분석 보고서

### REQ-008: 시장·제도 동향 보고서 제공
- **Type:** functional
- **Priority:** Medium
- **Description:** 시장·제도 동향 보고서를 제공한다.
- **Source:** Ⅱ. ESG 이슈 리서치 > 시장·제도 동향 보고서

### REQ-009: ESG 알림 서비스 제공
- **Type:** functional
- **Priority:** Medium
- **Description:** ESG 알림 서비스를 제공하여 주요 이슈·변동에 대해 통지한다.
- **Source:** Ⅱ. ESG 이슈 리서치 > ESG 알림 서비스

### REQ-010: 의안 분석 서비스
- **Type:** functional
- **Priority:** Low
- **Description:** 의안 분석 서비스를 제공한다.
- **Source:** Ⅲ. 추가기여 > 의안 분석

### REQ-011: ESG 투자전략 서비스
- **Type:** functional
- **Priority:** Medium
- **Description:** ESG 투자전략에 관한 서비스를 제공한다.
- **Source:** Ⅲ. 추가기여 > ESG 투자전략

### REQ-012: 세미나 개최 지원
- **Type:** functional
- **Priority:** Medium
- **Description:** 세미나 개최 및 운영 지원 서비스를 제공한다.
- **Source:** Ⅲ. 추가기여 > 세미나

### REQ-013: 자체평가모형 컨설팅
- **Type:** functional
- **Priority:** Medium
- **Description:** 자체평가모형 컨설팅 서비스를 제공한다.
- **Source:** Ⅲ. 추가기여 > 자체평가모형 컨설팅

### REQ-014: 채권 ESG 커스텀 방법론
- **Type:** functional
- **Priority:** Medium
- **Description:** 채권 ESG 평가에 사용할 커스텀 방법론을 설계하고 적용한다.
- **Source:** 4. 채권 ESG 평가 > 커스텀 방법론

### REQ-015: 채권 ESG 점수 산출
- **Type:** functional
- **Priority:** Medium
- **Description:** 채권 ESG 점수를 산출할 수 있는 방법론이 제공되어야 한다.
- **Source:** 4. 채권 ESG 평가 > 점수 산출

### REQ-016: 채권 ESG 순위 제시
- **Type:** functional
- **Priority:** Medium
- **Description:** 채권 ESG 순위를 제시할 수 있어야 한다.
- **Source:** 4. 채권 ESG 평가 > 순위 제시

### REQ-017: 제안서 PDF 제출
- **Type:** constraint
- **Priority:** High
- **Description:** 제안서는 PDF 형식으로 제출되어야 한다.
- **Source:** Ⅳ. 제안서 작성 > PDF 제출

### REQ-018: 제안서 구성 순서
- **Type:** constraint
- **Priority:** High
- **Description:** 제안서는 표지 → 서약서 → 본문 순으로 구성되어야 한다.
- **Source:** Ⅳ. 제안서 작성 > 표지 → 서약서 → 본문 순

### REQ-019: 본문 분량 30p 이내
- **Type:** constraint
- **Priority:** High
- **Description:** 제안서 본문은 30페이지 이내로 작성해야 한다.
- **Source:** Ⅳ. 제안서 작성 > 본문 30p 이내

### REQ-020: 협력사 명시
- **Type:** constraint
- **Priority:** Medium
- **Description:** 제안서에 협력사를 명시해야 한다.
- **Source:** Ⅳ. 제안서 작성 > 협력사 명시

### REQ-021: 증빙자료 필수
- **Type:** constraint
- **Priority:** Medium
- **Description:** 제안서 제출 시 증빙자료를 필수로 첨부해야 한다.
- **Source:** Ⅳ. 제안서 작성 > 증빙자료 필수

### REQ-022: 제출 후 수정 불가
- **Type:** constraint
- **Priority:** Medium
- **Description:** 제출 후 수정은 허용되지 않는다.
- **Source:** Ⅳ. 제안서 작성 > 제출 후 수정 불가

### REQ-023: 제안평가 기준 반영
- **Type:** constraint
- **Priority:** High
- **Description:** 제안평가 기준은 100점 만점 체계로 적용되어야 한다.
- **Source:** Ⅲ. 제안평가 기준

### REQ-024: 사업기간 준수
- **Type:** constraint
- **Priority:** Medium
- **Description:** 사업기간은 계약일로부터 명시된 종료일까지 준수해야 한다.
- **Source:** Ⅰ. 선정 개요 > 사업기간

### REQ-025: 첨부문서 제출 의무
- **Type:** constraint
- **Priority:** Medium
- **Description:** 제안서와 함께 제출해야 할 첨부문서(서약서, 일반현황, 재무현황, 투입 인력 계획)를 반드시 제출한다.
- **Source:** Ⅴ. 첨부 문서

