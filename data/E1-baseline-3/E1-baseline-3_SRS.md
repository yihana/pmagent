# Software Requirements Specification
**Project:** E1-baseline-3
**Generated:** 2025-11-19T00:40:04.954531

## 1. Requirements

### REQ-001: 웹접근성 전 영역 준수
- **Type:** non-functional
- **Priority:** High
- **Description:** 메인 사이트, 모바일, 인터넷뱅킹, Spectra, 고객센터 등 모든 대상에서 WCAG 2.0 AA 수준의 4원칙과 22항목을 적용하고 K-WAH 4.0으로 검증한다.
- **Source:** II. 세부수행내용 / (2) 접근성 준수

### REQ-002: 대체 텍스트 제공
- **Type:** non-functional
- **Priority:** High
- **Description:** 모든 이미지 콘텐츠에 대체 텍스트(ALT)가 부여되어 화면리더에서도 의미를 전달한다.
- **Source:** II. 세부수행내용 / (2) 접근성 준수

### REQ-003: 자막 제공
- **Type:** non-functional
- **Priority:** High
- **Description:** 동영상 콘텐츠에 자막(Closed Caption)을 제공하여 청각장애 사용자도 콘텐츠를 이해할 수 있다.
- **Source:** II. 세부수행내용 / (2) 접근성 준수

### REQ-004: 명도 대비 확보
- **Type:** non-functional
- **Priority:** High
- **Description:** 텍스트와 배경의 명도 대비 비율을 4.5:1 이상으로 보장한다.
- **Source:** II. 세부수행내용 / (2) 접근성 준수

### REQ-005: 키보드 접근성
- **Type:** non-functional
- **Priority:** High
- **Description:** 주요 기능은 모두 키보드로 접근 가능하고, 포커스 순서가 합리적으로 구성된다.
- **Source:** II. 세부수행내용 / (2) 접근성 준수

### REQ-006: 표 구조 접근성
- **Type:** non-functional
- **Priority:** Medium
- **Description:** 표는 시맨틱 마크업으로 구성하고 헤더는 필요한 경우 scope를 포함한다.
- **Source:** II. 세부수행내용 / (2) 접근성 준수

### REQ-007: 오류 정정 안내
- **Type:** non-functional
- **Priority:** Medium
- **Description:** 오류 메시지는 명확하고 접근성 친화적으로 제공되며, 제안된 수정 제안을 포함한다.
- **Source:** II. 세부수행내용 / (2) 접근성 준수

### REQ-008: Flash→JSP 변환
- **Type:** functional
- **Priority:** High
- **Description:** Flash(Flex) 콘텐츠를 JSP로 교체해 접근성과 유지보수를 개선한다.
- **Source:** II. 세부수행내용 / (5) 핵심 과제

### REQ-009: Spectra 화면 접근성
- **Type:** functional
- **Priority:** Medium
- **Description:** Spectra 외부 패키지 화면의 접근성을 개선하고 키보드/스크린리더 사용 가능성을 확보한다.
- **Source:** II. 세부수행내용 / (5) 핵심 과제

### REQ-010: 증명서/엑셀 다운로드 개선
- **Type:** functional
- **Priority:** Medium
- **Description:** 증명서 및 엑셀 다운로드 기능의 접근성을 개선하고 라벨링을 명확히 한다.
- **Source:** II. 세부수행내용 / (5) 핵심 과제

### REQ-011: 전자금융 접근성 보장
- **Type:** non-functional
- **Priority:** High
- **Description:** 전자금융 서비스에서 장애인 이용자도 거래 및 정보 열람이 가능하도록 한다.
- **Source:** II. 세부수행내용 / (2) 접근성 준수

### REQ-012: 구간암호화 모듈 교체
- **Type:** constraint
- **Priority:** High
- **Description:** 구간암호화 모듈(암호화 처리 컴포넌트)을 교체하고 보안 정책에 맞춘 구성을 적용한다.
- **Source:** II. 제안 기본사항 / 보안 정책 및 핵심 과제

### REQ-013: 개발환경 유지/최적안 제안
- **Type:** constraint
- **Priority:** Medium
- **Description:** 현 운영환경을 유지하거나 최적안을 제안하여 인프라와의 호환성을 확보한다.
- **Source:** II. 3. (1) 개발환경

### REQ-014: 보안정책 준수
- **Type:** non-functional
- **Priority:** High
- **Description:** 데이터 전송은 TLS 1.2 이상 및 HTTPS 강제를 포함한 보안 정책을 준수한다.
- **Source:** II. 제안 기본사항 / 보안 정책 준수

### REQ-015: 무상 유지보수 365x24
- **Type:** non-functional
- **Priority:** High
- **Description:** 무상 유지보수 서비스를 365×24로 제공하고 장애 대응을 보장한다.
- **Source:** II. 제안 기본사항 / 무상 유지보수

### REQ-016: 교육지원 필수
- **Type:** functional
- **Priority:** Medium
- **Description:** 교육지원이 필수이며, 교육 자료 제공 및 실무 교육을 수행한다.
- **Source:** II. 제안 기본사항 / 교육지원

### REQ-017: 산출물 소유권 발주처
- **Type:** constraint
- **Priority:** High
- **Description:** 제안 산출물의 지적 재산권은 발주처에 귀속되도록 한다.
- **Source:** IV. 참여조건 및 방법 / 산출물 소유권

### REQ-018: 하도급 제한
- **Type:** constraint
- **Priority:** Medium
- **Description:** 하도급은 발주처의 서면 동의 없이 허용되지 않는다.
- **Source:** IV. 참여조건 및 방법 / 하도급 제한

### REQ-019: 비밀유지
- **Type:** constraint
- **Priority:** High
- **Description:** 정보보호 및 기밀 유지에 관한 서약과 보안 정책 준수를 보장한다.
- **Source:** IV. 참여조건 및 방법 / 기밀 유지

### REQ-020: 문의는 이메일로
- **Type:** constraint
- **Priority:** Low
- **Description:** 문의 접수는 이메일 방식으로만 받으며, 응답은 명시된 SLA에 따른다.
- **Source:** IV. 참여조건 및 방법 / 문의: 이메일만 인정

### REQ-021: 인증마크 획득 지원
- **Type:** functional
- **Priority:** Medium
- **Description:** 인증마크 획득을 위한 컨설팅 및 증빙 자료 제공, 심사 대비를 지원한다.
- **Source:** II. 제안안내 / 인증마크 획득

### REQ-022: 제안서 형식 준수
- **Type:** non-functional
- **Priority:** Low
- **Description:** 제안서 작성은 PPT 형식으로 맑은 고딕체, 조견표 포함 등 제시 형식을 준수한다.
- **Source:** III. 제안안내 / 작성 방법

