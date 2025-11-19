# app/pages/pm_workflow.py
# 0.7 Scope → Schedule 통합 워크플로우
# 0.8 ReWOO 기반 Proposal End-to-End 데모 페이지

import json
from pathlib import Path
from datetime import datetime

import requests
import streamlit as st

st.set_page_config(page_title="ReWOO Proposal Workflow", layout="wide")

# ============================================
# 1. API Base 설정
# ============================================
API_BASE = st.secrets.get("API_BASE", "http://127.0.0.1:8001/api/v1/pm")
PROPOSAL_URL = f"{API_BASE}/proposal/rewoo"

st.title("📦 ReWOO Proposal Workflow")
st.caption("RFP 업로드 → Scope / Cost / Schedule / Change를 한 번에 생성하는 심층추론 파이프라인")

# ============================================
# 2. 입력 영역
# ============================================
with st.form("rewoo_proposal_form"):
    st.markdown("### 🔧 프로젝트 정보")

    col1, col2, col3 = st.columns(3)
    with col1:
        project_id = st.text_input("프로젝트 ID", value="20251119_101")
    with col2:
        project_name = st.text_input("프로젝트명", value="Demo Project")
    with col3:
        methodology = st.selectbox("방법론", ["waterfall", "agile"], index=0)

    st.markdown("### 📄 RFP 입력")
    col4, col5 = st.columns(2)
    with col4:
        uploaded_file = st.file_uploader("RFP 파일 업로드 (.txt, .md)", type=["txt", "md"])
    with col5:
        rfp_text = st.text_area(
            "또는 RFP 원문 텍스트 직접 입력",
            height=260,
            placeholder="제안요청서 본문을 붙여넣으세요."
        )

    st.markdown("### ⚙️ 심층추론 옵션")
    c1, c2, c3 = st.columns(3)
    with c1:
        refine_iterations = st.number_input("Scope Self-Refine 횟수", 0, 5, 2)
    with c2:
        max_time = st.number_input("Scope 최대 추론 시간(sec)", 30, 600, 120)
    with c3:
        min_quality = st.slider("최소 품질(LLM self-score)", 0.5, 0.99, 0.85, 0.01)

    c4, c5 = st.columns(2)
    with c4:
        use_got_schedule = st.checkbox("GoT 기반 일정 후보 탐색 사용", value=True)
    with c5:
        target_deadline = st.date_input("목표 완료일 (선택)", value=None, format="YYYY-MM-DD")

    submitted = st.form_submit_button("🚀 ReWOO Proposal 실행", type="primary")

# ============================================
# 3. 호출 & 결과 표시
# ============================================
if submitted:
    # RFP 텍스트 확보
    if uploaded_file is not None:
        try:
            file_text = uploaded_file.read().decode("utf-8")
        except Exception:
            st.error("업로드한 파일을 UTF-8로 읽을 수 없습니다. 인코딩을 확인해주세요.")
            st.stop()
        rfp_body = file_text.strip()
    else:
        rfp_body = (rfp_text or "").strip()

    if not rfp_body:
        st.error("RFP 텍스트가 없습니다. 파일 업로드 또는 텍스트 입력 중 하나는 필요합니다.")
        st.stop()

    payload = {
        "project_id": project_id,
        "project_name": project_name,
        "methodology": methodology,
        "rfp_text": rfp_body,
        "scope_options": {
            "refine_iterations": int(refine_iterations),
            "tot_constraints": {
                "max_time": float(max_time),
                "min_quality": float(min_quality),
            },
        },
        "schedule_options": {
            "use_got": bool(use_got_schedule),
            "target_deadline": target_deadline.isoformat() if target_deadline else None,
        },
    }

    st.info("📤 요청 Payload:")
    st.code(json.dumps(payload, ensure_ascii=False, indent=2), language="json")

    try:
        with st.spinner("ReWOO Proposal 파이프라인 실행 중..."):
            res = requests.post(PROPOSAL_URL, json=payload, timeout=300)
    except Exception as e:
        st.error(f"❌ ReWOO Proposal API 호출 실패: {e}")
        st.stop()

    if res.status_code != 200:
        st.error(f"❌ ReWOO Proposal API 오류: {res.status_code}")
        st.code(res.text)
        st.stop()

    data = res.json()
    st.success("✅ ReWOO Proposal 생성 완료")

    # ----------------------------------------
    # 3-1. Summary 카드
    # ----------------------------------------
    summary = data.get("summary", {})
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("요구사항 수", summary.get("requirements_count", "–"))
    with col2:
        total_cost = summary.get("total_cost")
        st.metric("총 예상비용", f"{total_cost:,.0f} 원" if isinstance(total_cost, (int, float)) else "–")
    with col3:
        duration = summary.get("schedule_duration")
        st.metric("예상 기간(일)", duration if duration is not None else "–")

    st.markdown("---")

    # ----------------------------------------
    # 3-2. Scope / Cost / Schedule 섹션
    # ----------------------------------------
    scope_out = data.get("scope", {})
    cost_out = data.get("cost", {})
    sched_out = data.get("schedule", {})

    # Scope
    with st.expander("📗 Scope / Requirements 상세", expanded=True):
        reqs = scope_out.get("requirements", [])
        st.write(f"요구사항 {len(reqs)}개")
        if reqs:
            st.table([
                {
                    "ID": r.get("req_id"),
                    "Type": r.get("type"),
                    "Title": r.get("title") or r.get("summary"),
                }
                for r in reqs[:30]
            ])
            if len(reqs) > 30:
                st.caption(f"... 외 {len(reqs) - 30}개")

    # Cost
    with st.expander("💰 Cost 추정 결과"):
        if cost_out:
            st.json(cost_out)
        else:
            st.info("비용 추정 결과 없음")

    # Schedule (GoT 후보 포함)
    with st.expander("📅 Schedule / GoT 후보 스케줄"):
        best_plan = sched_out.get("best_plan") or sched_out.get("plan")
        best_strategy = sched_out.get("best_strategy")
        candidates = sched_out.get("candidates") or []

        if best_plan:
            st.markdown("#### 🏆 선택된 최적 스케줄 (Best Plan)")
            st.json(best_plan)

        if best_strategy:
            st.markdown("#### ⚙️ 선택된 전략 (Best Strategy)")
            st.json(best_strategy)

        if candidates:
            st.markdown("#### 🤖 GoT 후보 스케줄 리스트")
            rows = []
            for c in candidates:
                rows.append({
                    "Score": round(c.get("score", 0), 4),
                    "Parallel": c.get("strategy", {}).get("parallel_factor"),
                    "Buffer": c.get("strategy", {}).get("buffer_ratio"),
                    "Duration": c.get("plan_summary", {}).get("total_duration"),
                })
            st.table(rows)
        else:
            st.info("GoT 후보 스케줄 정보 없음")

    # ----------------------------------------
    # 3-3. Raw JSON
    # ----------------------------------------
    with st.expander("🔍 전체 응답 (Raw JSON)"):
        st.json(data)

    # Debug
    st.markdown("---")
    st.caption(f"API_BASE = {API_BASE}")
    st.caption(f"PROPOSAL_URL = {PROPOSAL_URL}")
