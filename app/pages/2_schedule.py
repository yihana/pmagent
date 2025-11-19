# app/pages/pm_schedule.py
# TO-BE: Schedule Agent 전용 페이지
import streamlit as st
import requests
import json
from datetime import datetime
from pathlib import Path
import matplotlib.pyplot as plt
import streamlit.components.v1 as components  # 🔥 HTML 임베딩용

API_BASE = st.secrets.get("API_BASE", "http://127.0.0.1:8001/api/v1/pm")

st.title("📅 Schedule Agent — 일정 생성")

# ============================================
# 1. 입력 폼
# ============================================
with st.form("schedule_form"):
    st.markdown("### 프로젝트 정보")
    
    # ✅ Scope에서 전달된 정보 자동 로드
    default_prj_id = st.session_state.get("project_id", "20251119_101")
    default_prj_nm = st.session_state.get("project_name", "Demo Project")
    default_methodology = st.session_state.get("methodology", "waterfall")
    default_wbs = st.session_state.get("wbs_json_path", "")
    
    col1, col2, col3 = st.columns(3)

    with col1:
        project_id = st.text_input(
            "프로젝트 ID",
            value=default_prj_id
        )
        st.session_state["project_id"] = project_id  # 🔥 저장

    with col2:
        project_name = st.text_input(
            "프로젝트명",
            value=default_prj_nm
        )
        st.session_state["project_name"] = project_name

    with col3:
        methodology = st.selectbox("방법론", ["waterfall", "agile"], index=0)
    
    st.markdown("### 입력 파일 경로")
    col1, col2 = st.columns(2)
    with col1:
        req_json_path = st.text_input(
            "requirements.json 경로",
            value=str(Path("data") / project_id / "requirements.json"),
            help="Scope Agent에서 생성된 요구사항 파일 경로"
        )
    with col2:
        wbs_json_path = st.text_input(
            "WBS JSON 경로",
            value=str(Path("data") / project_id / "wbs_structure.json"),
            help="Scope Agent에서 생성된 WBS JSON 파일 경로"
        )
    
    if default_wbs and wbs_json_path == default_wbs:
        st.success("✅ Scope에서 전달된 WBS를 사용합니다.")
    
    st.markdown("### 일정 설정")
    col3, col4 = st.columns(2)
    with col3:
        start_date = st.date_input("시작일", value=datetime.today())
    with col4:
        sprint_length = st.number_input("Sprint 길이(주)", 1, 4, 2)
    
    estimation_mode = st.selectbox("추정 모드", ["heuristic", "llm"], index=0)
    
    submitted = st.form_submit_button("📅 Schedule 생성 실행", type="primary")

# ============================================
# 2. Schedule 실행
# ============================================
if submitted:
    if not wbs_json_path.strip():
        st.error("❌ WBS JSON 경로를 입력하세요.")
        st.info("💡 먼저 Scope 페이지에서 WBS를 생성하세요.")
        st.stop()
    
    payload = {
        "project_id": project_id,
        "methodology": methodology,
        "requirements_json": req_json_path,
        "wbs_json": wbs_json_path,
        "calendar": {"start_date": start_date.isoformat()},
        "sprint_length_weeks": sprint_length,
        "estimation_mode": estimation_mode
    }
    
    st.info("📤 요청: " + json.dumps(payload, ensure_ascii=False))
    
    try:
        with st.spinner("Schedule Agent 실행 중..."):
            resp = requests.post(f"{API_BASE}/schedule/analyze", json=payload, timeout=180)
            data = resp.json()
    except Exception as e:
        st.error(f"❌ API 호출 실패: {e}")
        st.stop()
    
    # ============================================
    # 3. 결과 표시
    # ============================================
    if resp.status_code == 200:
        st.success("✅ Schedule 생성 완료")
        
        method = data.get("methodology", methodology)
        
        # Waterfall 결과
        if method == "waterfall":
            st.subheader("📊 Waterfall 결과")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                plan_csv = data.get("plan_csv")
                if plan_csv:
                    st.markdown("**Plan CSV**")
                    st.code(plan_csv)
            
            with col2:
                gantt_json = data.get("gantt_json")
                if gantt_json:
                    st.markdown("**Gantt JSON**")
                    st.code(gantt_json)
                    
                    # Gantt 미리보기
                    try:
                        if Path(gantt_json).exists():
                            with open(gantt_json, "r", encoding="utf-8") as f:
                                gj = json.load(f)
                            tasks = gj.get("tasks", [])
                            if tasks:
                                with st.expander("📅 Gantt 미리보기"):
                                    st.table([
                                        {
                                            "ID": t["id"],
                                            "Name": t["name"],
                                            "Start": t.get("start", ""),
                                            "End": t.get("end", "")
                                        }
                                        for t in tasks[:10]
                                    ])
                    except Exception as e:
                        st.warning(f"Gantt 로드 실패: {e}")
            
            with col3:
                # Critical Path 처리 (기존 텍스트 버전)
                cp_data = data.get("critical_path")
                cp_list = []
                
                if isinstance(cp_data, str):
                    # 파일 경로인 경우
                    try:
                        if Path(cp_data).exists():
                            with open(cp_data, "r", encoding="utf-8") as f:
                                cp_json = json.load(f)
                                cp_list = cp_json.get("critical_path", [])
                    except:
                        pass
                elif isinstance(cp_data, list):
                    cp_list = cp_data
                
                st.markdown("**Critical Path (텍스트 요약)**")
                if cp_list:
                    st.metric("주요 경로 작업 수", len(cp_list))
                    with st.expander("📍 Critical Path 상세"):
                        # task가 dict이든 str이든 최대한 유연하게 처리
                        for task in cp_list[:10]:
                            if isinstance(task, dict):
                                name = task.get("name") or task.get("id")
                            else:
                                name = str(task)
                            st.text(f"• {name}")
                else:
                    st.info("Critical Path 정보 없음")

            # ----------------------------------------
            # 🔥 GoT 기반 후보 스케줄 / 전략 비교
            # ----------------------------------------
            st.markdown("---")
            st.subheader("🤖 GoT 기반 후보 스케줄 (있을 경우)")
            got_best_plan = data.get("best_plan") or data.get("schedule_got", {}).get("best_plan")
            got_best_strategy = data.get("best_strategy") or data.get("schedule_got", {}).get("best_strategy")
            got_candidates = data.get("candidates") or data.get("schedule_got", {}).get("candidates", [])

            if got_candidates:
                rows = []
                for c in got_candidates:
                    # E.g. {"score": s, "strategy": {...}, "plan_summary": {...}}
                    score = c.get("score")
                    strat = c.get("strategy", {})
                    summary = c.get("plan_summary", {})
                    rows.append({
                        "Score": round(score, 4) if isinstance(score, (int, float)) else score,
                        "Parallel": strat.get("parallel_factor"),
                        "Buffer": strat.get("buffer_ratio"),
                        "Duration": summary.get("total_duration"),
                    })
                st.table(rows)
            else:
                st.info("GoT 후보 스케줄 정보 없음 (일반 스케줄만 생성된 경우일 수 있음)")

            if got_best_plan:
                with st.expander("🏆 선택된 최적 스케줄 (Best Plan) 상세"):
                    st.json(got_best_plan)
            if got_best_strategy:
                with st.expander("⚙️ 선택된 전략 (Best Strategy) 상세"):
                    st.json(got_best_strategy)

            # ----------------------------------------
            # 🔥 Critical Path 그래프 시각화 (HTML/PNG)
            #  - change_mgmt.py에서 생성한 output과 연동
            # ----------------------------------------
            st.markdown("---")
            st.subheader("📈 Critical Path 시각화")

            # 1) 최상위 필드에서 찾기
            cp_html = data.get("critical_path_html")
            cp_png = data.get("critical_path_png")

            # 2) 혹시 change_mgmt 블럭이 있다면 그 안에서 찾기
            change_block = data.get("change_mgmt") or data.get("change_management")
            if change_block:
                cp_html = cp_html or change_block.get("critical_path_html")
                cp_png = cp_png or change_block.get("critical_path_png")

            shown = False

            if cp_html:
                p = Path(cp_html)
                if p.exists():
                    try:
                        with p.open("r", encoding="utf-8") as f:
                            html_str = f.read()
                        components.html(html_str, height=600, scrolling=True)
                        shown = True
                    except Exception as e:
                        st.warning(f"Critical Path HTML 로드 실패: {e}")

            if not shown and cp_png:
                p = Path(cp_png)
                if p.exists():
                    try:
                        st.image(str(p), caption="Critical Path (PNG)")
                        shown = True
                    except Exception as e:
                        st.warning(f"Critical Path PNG 로드 실패: {e}")

            if not shown:
                st.info("Critical Path 시각화 파일(HTML/PNG)을 찾지 못했습니다.")

        # Agile 결과
        elif method == "agile":
            st.subheader("🔄 Agile 결과")
            
            col1, col2 = st.columns(2)
            with col1:
                burndown = data.get("burndown_json")
                if burndown:
                    st.markdown("**Burndown JSON**")
                    st.code(burndown)
                    
                    # Burndown 차트
                    try:
                        if Path(burndown).exists():
                            with open(burndown, "r", encoding="utf-8") as f:
                                bd = json.load(f)
                            
                            points = bd.get("burndown", [])
                            if points:
                                by_day = {}
                                for p in points:
                                    day = p.get("day", 0)
                                    rem = p.get("remaining_sp", 0)
                                    by_day[day] = rem
                                
                                xs = sorted(by_day.keys())
                                ys = [by_day[x] for x in xs]
                                
                                fig, ax = plt.subplots(figsize=(8, 4))
                                ax.plot(xs, ys, marker='o')
                                ax.set_title("Sprint Burndown")
                                ax.set_xlabel("Day")
                                ax.set_ylabel("Remaining SP")
                                ax.grid(True, alpha=0.3)
                                st.pyplot(fig)
                    except Exception as e:
                        st.warning(f"Burndown 로드 실패: {e}")
            
            with col2:
                sprint_count = data.get("data", {}).get("sprint_count")
                if sprint_count:
                    st.metric("Sprint 수", sprint_count)
        

        # Timeline 미리보기 1117
        timeline_path = data.get("timeline_path")

        if timeline_path:
            with st.expander("📈 Timeline 미리보기"):
                try:
                    p = Path(timeline_path)
                    if p.exists():
                        with p.open("r", encoding="utf-8") as f:
                            tl = json.load(f)

                        tasks = tl.get("tasks", [])
                        if tasks:
                            st.table([
                                {
                                    "ID": t.get("id"),
                                    "Name": t.get("name"),
                                    "ES": t.get("ES"),
                                    "EF": t.get("EF")
                                }
                                for t in tasks[:10]
                            ])
                except Exception as e:
                    st.warning(f"Timeline 로드 실패: {e}")

        
        # 전체 응답
        with st.expander("🔍 전체 응답 (JSON)"):
            st.json(data)
    
    else:
        st.error(f"❌ Schedule API 오류: {resp.status_code}")
        st.code(resp.text)

# ============================================
# 4. 사이드바
# ============================================
with st.sidebar:
    st.markdown("### ℹ️ 정보")
    
    if st.session_state.get("wbs_json_path"):
        st.success("✅ WBS 경로 로드됨")
        st.caption(st.session_state["wbs_json_path"])
    else:
        st.warning("⚠️ WBS 없음")
        st.caption("Scope 페이지에서 먼저 WBS를 생성하세요.")
    
    st.markdown("---")
    st.caption(f"API: {API_BASE}")
