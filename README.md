# PM Agent  
> LLM 기반 심층추론(Deep Reasoning) PM 오토메이션 플랫폼

PM Agent는 실제 RFP(제안요청서)를 입력으로 받아,

- **요구사항 추출 (Scope Agent)**
- **비용 추정 (Cost Agent)**
- **일정 계획 및 Critical Path/GoT 후보 탐색 (Schedule Agent)**
- **End-to-End Proposal 오케스트레이션 (Meta-Planner / ReWOO 스타일)**

까지 한 번에 수행하는 **End-to-End 프로젝트 제안 자동화 에이전트 플랫폼**입니다.

##  주요 특징

- **Scope Agent**
  - Tree-of-Thoughts(ToT) 기반 전략 선택
  - Self-Refine Loop(최대 N회)로 품질 자동 보정
  - 기능/비기능/제약 요구사항 분류
  - WBS, RTM, SRS 등 PM 산출물 자동 생성

- **Cost Agent**
  - 요구사항/작업량 기반 휴리스틱 비용 계산
  - 개발/테스트/PM/기타로 비용 분해

- **Schedule Agent**
  - WBS 기반 일정 생성
  - DAG + Critical Path 계산
  - GoT(ScheduleGoT) 기반 후보 스케줄 탐색

- **Meta-Planner (ReWOO 스타일)**
  - Scope → Cost → Schedule → (Risk/Integrator) 흐름 오케스트레이션
  - 실패 시 재시도 및 요약/Refine 전략 적용

- **Experiments (E1~E4)**
  - E1: Baseline(규칙) vs PM Agent(LLM) – 요구사항 수/시간 비교
  - E2: Heuristic vs GoT – 일정 품질 비교
  - E3: Efficiency – Time Overhead 분석
  - E4: End-to-End Proposal – 비용/기간/요구사항 통계

- **UI**
  - Streamlit 기반 대시보드
  - ReWOO Proposal Workflow 페이지에서 RFP 업로드 → 결과 확인까지 one-click 실행

##  프로젝트 구조 (요약)
pm-agent/
├─ app/
│  ├─ main.py                  # Streamlit 메인 앱
│  └─ pages/
│     ├─ 0_workflow.py         # PM Workflow / Meta-Planner 데모
│     ├─ pm_workflow.py        # ReWOO Proposal Workflow 페이지
│     ├─ 3_risk.py             # Risk Agent 페이지(스켈레톤)
│     └─ pm_agent_dashboard.py # 회의/변경 흐름 대시보드
├─ server/
│  ├─ main.py                  # FastAPI 엔트리포인트
│  ├─ routers/
│  │  └─ pm_work.py            # /api/v1/pm/* 라우트 (ReWOO Proposal 등)
│  └─ workflow/
│     ├─ pm_deep_reasoning.py  # MinimalPMGraph / Deep Reasoning Pipeline
│     ├─ meta_planner.py       # Meta-Planner (ReWOO 스타일)
│     ├─ pm_graph.py           # 기존 PM 그래프 실행기
│     ├─ agents/
│     │  ├─ scope_agent/
│     │  │  ├─ pipeline.py     # Scope Agent 메인 로직
│     │  │  ├─ tot_strategy_selector.py
│     │  │  ├─ self_refine.py
│     │  │  └─ prompts.py
│     │  ├─ cost_agent/
│     │  │  └─ cost_agent.py   # 비용 추정
│     │  └─ schedule_agent/
│     │     ├─ pipeline.py     # 일정 생성 (DAG/CP)
│     │     └─ got_scheduler.py# ScheduleGoT
│     └─ insight_integrator/
│        ├─ pm_analyzer.py     # 로그/실험/결과 분석
│        └─ pm_report.py       # 보고서/요약 텍스트 생성기
└─ experiments/
   ├─ run_experiments.py       # E1~E4 실험 러너
   └─ rfp_samples/             # 실험용 RFP 텍스트
설치 및 실행
1. 필수 요구사항
•	Python 3.10+
•	pip / virtualenv
2. 프로젝트 설치
1) 저장소 클론
git clone <YOUR_REPO_URL> pm-agent
cd pm-agent
2) 가상환경 생성 및 활성화 (Windows PowerShell 예시)
python -m venv .venv
.\.venv\Scripts\activate
3) 패키지 설치
pip install -r requirements.txt
3. 환경 변수 설정
server/utils/config.py 또는 .env 등을 사용하여 LLM 및 DB 관련 환경을 설정합니다.
▶ 백엔드(FastAPI) 실행
# 프로젝트 루트에서
.\.venv\Scripts\activate
uvicorn server.main:app --reload --port 8001
▶ 프론트엔드(Streamlit) 실행
# 프로젝트 루트에서
.\.venv\Scripts\activate
streamlit run app/main.py --server.port 8501
•	브라우저에서 http://localhost:8501 접속
•	좌측 메뉴에서:
o	PM Workflow 
o	Scope / Schedule / Risk / Dashboard 등을 선택
▶ 사용법 및 예제
1. ReWOO Proposal Workflow (추천 데모)
1) pm_workflow.py 페이지 선택
2) 입력:
- 프로젝트 ID, 프로젝트명, 방법론(waterfall/agile)
- RFP 파일 업로드(.txt, .md) 또는 원문 텍스트 붙여넣기
- Self-Refine 횟수, 최대 추론 시간, 최소 품질(LLM self-score)
- GoT 사용 여부(체크박스) 및 목표 완료일(옵션)
3) ReWOO Proposal 실행 버튼 클릭
4) 출력:
- 요구사항 개수, 총 비용, 예상 기간(일)
- 요구사항 테이블
- 비용 계산 결과(JSON)
- 일정/GoT 후보 스케줄
- Raw JSON 응답 및 Manifest 파일 경로
2. Deep Reasoning Pipeline 단독 실행
Scope → Schedule 순으로 간단 실행

3. 정량 실험(E1~E4) 재현
cd experiments
python -m experiments.run_experiments
experiments/rfp_samples/*.txt 에 있는 RFP들을 기준으로:
E1: Baseline(규칙) vs PM Agent(LLM)
E2: Heuristic vs GoT 일정 비교
E3: 시간 효율성 비교
E4: End-to-End Proposal (요구사항/비용/기간)
결과:
콘솔 로그 + experiments/results/ 폴더 내 JSON/PNG 그래프 생성
E1_true_baseline.png등 차트를 보고 발표자료에 활용 가능	

▶ API 문서
실제 엔드포인트는 `server/routers/pm_work.py` 를 기준으로 확인하세요.
아래는 주요 엔드포인트 예시입니다.
1. ReWOO Proposal API
POST /api/v1/pm/proposal/rewoo
Content-Type: application/json
**Request Body 예시**
{
"project_id": "20251119_101",
"project_name": "Demo Project",
"methodology": "waterfall",
"rfp_text": "... RFP 전문 ...",
"scope_options": {
"refine_iterations": 2,
"tot_constraints": {
"max_time": 120.0,
"min_quality": 0.85
}
},
"schedule_options": {
"use_got": true,
"target_deadline": "2025-11-30"
}
}
**Response 예시(요약)**
{
"summary": {
"requirements_count": 24,
"total_cost": 15985714,
"schedule_duration": 69
},
"scope": {
"requirements": [ ... ],
"wbs": { ... },
"rtm_path": "data/.../rtm.xlsx"
},
"cost": { ... },
"schedule": {
"plan": { ... },
"critical_path": [ ... ],
"best_plan": { ... },
"candidates": [ ... ]
},
"manifest": {
"path": "data/.../manifest.json"
}
}
2. Scope / Schedule 개별 API
POST /api/v1/scope/run
POST /api/v1/schedule/run


▶ 기여 방법 및 라이선스
라이선스
이 프로젝트의 라이선스는 **프로젝트 소유자에 의해 결정**됩니다.
외부 공개/상용 사용을 계획하는 경우, 별도의 라이선스 정책을 협의 후 적용해야 합니다.
