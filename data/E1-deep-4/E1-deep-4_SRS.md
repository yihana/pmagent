# Software Requirements Specification
**Project:** E1-deep-4
**Generated:** 2025-11-19T00:42:29.847355

## 1. Requirements

### REQ-001: ESG 평가대상 범위
- **Type:** functional
- **Priority:** High
- **Description:** ESG 평가대상은 KOSPI 및 KOSDAQ100 포함 약 1,000개 기업으로 정의하고, 원점수 및 산출근거를 포함한 데이터를 제공한다.
- **Source:** Ⅱ. 제안요청 내용 > 1. ESG 평가데이터 > 1.1 평가대상

### REQ-002: 원점수 및 근거 제공
- **Type:** functional
- **Priority:** High
- **Description:** 환경/사회/지배구조 항목에 대한 원점수와 산출근거를 함께 제공한다.
- **Source:** Ⅱ. 제안요청 내용 > 1. ESG 평가데이터

### REQ-003: 이슈별 점수 제공
- **Type:** functional
- **Priority:** High
- **Description:** ESG 이슈 리포트에서 이슈별 점수를 명시적으로 제공한다.
- **Source:** Ⅱ. 제안요청 내용 > 1. ESG 평가데이터

### REQ-004: 종합 등급 및 순위 제공
- **Type:** functional
- **Priority:** High
- **Description:** ESG 종합 등급 및 기업별 순위를 산출하고 제공한다.
- **Source:** Ⅱ. 제안요청 내용 > 1. ESG 평가데이터

### REQ-005: 제공 주기 연 2회
- **Type:** constraint
- **Priority:** High
- **Description:** ESG 평가 데이터는 연 2회(6월, 11월) 제공한다.
- **Source:** Ⅱ. 제안요청 내용 > 1. ESG 평가데이터

### REQ-006: 대상: 약 1,000개
- **Type:** functional
- **Priority:** Medium
- **Description:** 대상은 벤치마크 구성 종목 전체 약 1,000개 기업으로 확정한다.
- **Source:** Ⅱ. 제안요청 내용 > 1. ESG 이슈 리서치

### REQ-007: 기업별 ESG 분석 보고서
- **Type:** functional
- **Priority:** High
- **Description:** 기업별 ESG 분석 보고서를 제공한다.
- **Source:** Ⅱ. 제안요청 내용 > 2. ESG 이슈 리서치

### REQ-008: 컨트러버시 분석 보고서
- **Type:** functional
- **Priority:** High
- **Description:** 컨트러버시(이슈) 분석 보고서를 제공한다.
- **Source:** Ⅱ. 제안요청 내용 > 2. ESG 이슈 리서치

### REQ-009: 시장·제도 동향 보고서
- **Type:** functional
- **Priority:** Medium
- **Description:** 시장 및 제도 동향 보고서를 제공한다.
- **Source:** Ⅱ. 제안요청 내용 > 2. ESG 이슈 리서치

### REQ-010: ESG 알림 서비스
- **Type:** functional
- **Priority:** Medium
- **Description:** ESG 관련 이슈 알림 서비스를 제공한다.
- **Source:** Ⅱ. 제안요청 내용 > 2. ESG 이슈 리서치

### REQ-011: 채권 ESG 평가 커스텀
- **Type:** functional
- **Priority:** Medium
- **Description:** 채권 ESG 평가에 대해 커스텀 방법론을 제공한다.
- **Source:** Ⅱ. 제안요청 내용 > 4. 채권 ESG 평가

### REQ-012: 채권 ESG 평가 점수
- **Type:** functional
- **Priority:** Medium
- **Description:** 커스텀 방법론에 따른 점수를 산출한다.
- **Source:** Ⅱ. 제안요청 내용 > 4. 채권 ESG 평가

### REQ-013: 채권 ESG 평가 순위
- **Type:** functional
- **Priority:** Medium
- **Description:** 채권 ESG 평가의 순위를 제시한다.
- **Source:** Ⅱ. 제안요청 내용 > 4. 채권 ESG 평가

### REQ-014: 의안 분석 제공
- **Type:** functional
- **Priority:** Medium
- **Description:** 의안 분석 서비스를 제공한다.
- **Source:** Ⅱ. 제안요청 내용 > 3. 추가기여

### REQ-015: ESG 투자전략 제공
- **Type:** functional
- **Priority:** Medium
- **Description:** ESG 투자전략에 대한 제안 및 분석을 제공한다.
- **Source:** Ⅱ. 제안요청 내용 > 3. 추가기여

### REQ-016: 세미나 개최
- **Type:** functional
- **Priority:** Medium
- **Description:** ESG 관련 세미나를 주최하거나 공동 개최한다.
- **Source:** Ⅱ. 제안요청 내용 > 3. 추가기여

### REQ-017: 자체평가모형 컨설팅
- **Type:** functional
- **Priority:** Medium
- **Description:** 자체평가모형 컨설팅을 제공한다.
- **Source:** Ⅱ. 제안요청 내용 > 3. 추가기여

### REQ-018: 제안평가 기준 반영
- **Type:** constraint
- **Priority:** High
- **Description:** 제안평가 기준(경영안정성, 리서치 조직 전문성 등 100점 만점) 반영 및 점수 산정 기준을 준수한다.
- **Source:** Ⅲ. 제안평가 기준 (100점)

### REQ-019: 제안서 형식 제출
- **Type:** constraint
- **Priority:** High
- **Description:** 제안서는 PDF 형식으로 제출하고, 표지/서약서/본문 순으로 구성한다.
- **Source:** Ⅳ. 제안서 작성

### REQ-020: 협력사 명시
- **Type:** constraint
- **Priority:** Medium
- **Description:** 제안서 본문에 협력사를 명시한다.
- **Source:** Ⅳ. 제안서 작성

### REQ-021: 본문 30p 이내
- **Type:** constraint
- **Priority:** Medium
- **Description:** 제안서 본문은 30페이지 이내로 작성한다.
- **Source:** Ⅳ. 제안서 작성

### REQ-022: 증빙자료 필수 제출
- **Type:** constraint
- **Priority:** Medium
- **Description:** 증빙자료를 필수로 제출한다.
- **Source:** Ⅳ. 제안서 작성

### REQ-023: 제출 후 수정 불가
- **Type:** constraint
- **Priority:** Medium
- **Description:** 제출 후에는 수정이 불가하다.
- **Source:** Ⅳ. 제안서 작성

### REQ-024: 첨부문서 제출
- **Type:** constraint
- **Priority:** Medium
- **Description:** 첨부문서(일반현황, 재무현황, 투입 인력 계획)를 제출한다.
- **Source:** Ⅳ. 제안서 작성

