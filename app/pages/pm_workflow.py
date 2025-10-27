# app/pages/pm_workflow.py
# TO-BE: Scope → Schedule 통합 워크플로우
import streamlit as st
import requests
import json
from datetime import datetime

API_BASE = st.secrets.get("API_BASE", "http://127.0.0.1:8001/api/v1/pm")

st.title("🔄 Workflow — Scope → Schedule 통합")

st.markdown("""
이 페이지는 **Scope 추출**과 **Schedule 생성**을 한 번에 실행합니다.

**장점:**
- RFP 업로드 → WBS 생성 → 일정 계획까지 원클릭
- 중간 결과 확인 불필요
- 빠른 프로토타이핑에 적합
""")

# ============================================
# 1. 입력 폼
# ============================================
with st.form("workflow_form"):
    st.markdown("### 1️⃣ Scope 설정")
    col1, col2 = st.columns(2)
    with col1:
        project_name = st.text_input("프로젝트명", "Demo Project")
    with col2:
        methodology = st.selectbox("방법론", ["waterfall", "agile"])
    
    rfp_path = st.text_input(
        "RFP 파일 경로",
        "data/inputs/RFP/sample_rfp.pdf"
    )
    
    st.markdown("### 2️⃣ Schedule 설정")
    col3, col4 = st.columns(2)
    with col3:
        start_date = st.date_input("시작일", datetime.today())
    with col4:
        sprint_length = st.number_input("Sprint 길이(주)", 1, 4, 2)
    
    submitted = st.form_submit_button("🚀 통합 실행", type="primary")

# ============================================
# 2. 워크플로우 실행
# ============================================
if submitted:
    if not rfp_path.strip():
        st.error("❌ RFP 파일 경로를 입력하세요.")
        st.stop()
    
    # Payload 구성
    payload = {
        "scope": {
            "project_name": project_name,
            "methodology": methodology,
            "documents": [{"path": rfp_path, "type": "RFP"}],
            "options": {"chunk_size": 500, "overlap": 100}
        },
        "schedule": {
            "methodology": methodology,
            "calendar": {"start_date": start_date.isoformat()},
            "sprint_length_weeks": sprint_length
        }
    }
    
    st.info("📤 요청: " + json.dumps(payload, ensure_ascii=False, indent=2))
    
    # Progress bar
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    try:
        status_text.text("1/2 Scope Agent 실행 중...")
        progress_bar.progress(0.3)
        
        resp = requests.post(
            f"{API_BASE}/workflow/scope-then-schedule",
            json=payload,
            timeout=300
        )
        
        progress_bar.progress(0.9)
        status_text.text("2/2 결과 처리 중...")
        
        data = resp.json()
        progress_bar.progress(1.0)
        status_text.text("✅ 완료!")
        
    except Exception as e:
        st.error(f"❌ 워크플로우 실패: {e}")
        st.stop()
    
    # ============================================
    # 3. 결과 표시
    # ============================================
    if resp.status_code == 200:
        st.success("✅ 워크플로우 완료")
        
        # Scope 결과
        scope_result = data.get("scope", {})
        if scope_result:
            with st.expander("📋 Scope 결과", expanded=True):
                col1, col2 = st.columns(2)
                with col1:
                    wbs = scope_result.get("wbs_json")
                    if wbs:
                        st.text(f"✅ WBS: {wbs}")
                with col2:
                    rtm = scope_result.get("rtm_csv")
                    if rtm:
                        st.text(f"✅ RTM: {rtm}")
        
        # Schedule 결과
        schedule_result = data.get("schedule", {})
        if schedule_result:
            with st.expander("📅 Schedule 결과", expanded=True):
                col1, col2 = st.columns(2)
                with col1:
                    gantt = schedule_result.get("gantt_json")
                    if gantt:
                        st.text(f"✅ Gantt: {gantt}")
                with col2:
                    plan = schedule_result.get("plan_csv")
                    if plan:
                        st.text(f"✅ Plan: {plan}")
        
        # 전체 응답
        with st.expander("🔍 전체 응답 (JSON)"):
            st.json(data)
    
    else:
        st.error(f"❌ Workflow API 오류: {resp.status_code}")
        st.code(resp.text)

# ============================================
# 4. 사이드바 가이드
# ============================================
with st.sidebar:
    st.markdown("### 📖 사용 가이드")
    st.markdown("""
    **단계:**
    1. 프로젝트 정보 입력
    2. RFP 파일 경로 지정
    3. 일정 설정
    4. "통합 실행" 클릭
    
    **결과:**
    - Scope: WBS, RTM, 범위기술서
    - Schedule: Gantt, Plan, Critical Path
    """)
    
    st.markdown("---")
    st.caption(f"API: {API_BASE}")