# pm_agent_schedule.py (Streamlit page)
import streamlit as st
import requests
import json
from datetime import datetime
import matplotlib.pyplot as plt

API_BASE = st.secrets.get("API_BASE", "http://127.0.0.1:8001/api/v1/pm")

st.title("PM Agent — Schedule 생성 (Waterfall / Agile)")

with st.form("schedule_form"):
    project_id = st.text_input("Project ID", value="Demo Project")
    methodology = st.radio("Methodology", options=["waterfall", "agile"], index=0)
    wbs_json_path = st.text_input("WBS JSON 파일 경로 또는 JSON 문자열", "")
    start_date = st.date_input("Workflow 시작일 (YYYY-MM-DD)", value=datetime.today())
    sprint_length_weeks = st.number_input("Sprint 길이(주, agile 전용)", min_value=1, value=2)
    estimation_mode = st.selectbox("Estimation Mode", options=["heuristic", "llm"], index=0)
    submitted = st.form_submit_button("Schedule 생성 실행")

if submitted:
    payload = {
        "project_id": project_id,
        "methodology": methodology,
        "wbs_json": wbs_json_path,
        "calendar": {"start_date": start_date.isoformat()},
        "sprint_length_weeks": int(sprint_length_weeks),
        "estimation_mode": estimation_mode
    }
    st.info("요청: " + json.dumps(payload, ensure_ascii=False))
    try:
        resp = requests.post(f"{API_BASE}/schedule/analyze", json=payload, timeout=60)
        data = resp.json()
    except Exception as e:
        st.error(f"API 호출 실패: {e}")
        st.stop()

    st.success("Schedule 생성 완료")
    st.json(data)

    # Waterfall: show gantt / critical path link
    method = data.get("methodology")
    if method == "waterfall":
        st.subheader("Waterfall 결과")
        plan_csv = data.get("plan_csv")
        gantt_json = data.get("gantt_json")
        cp = data.get("critical_path")
        st.markdown(f"- Plan CSV: `{plan_csv}`")
        st.markdown(f"- Gantt JSON: `{gantt_json}`")
        st.markdown(f"- Critical Path: `{cp}`")
        # try to load gantt and render simple table
        if gantt_json:
            try:
                with open(gantt_json, "r", encoding="utf-8") as f:
                    gj = json.load(f)
                st.table([{"id":t["id"], "name":t["name"], "start":t["start"], "end":t["end"]} for t in gj.get("tasks",[])])
            except Exception as e:
                st.warning("gantt 로드 실패: " + str(e))

    elif method == "agile":
        st.subheader("Agile 결과")
        burndown = data.get("burndown_json")
        sprint_count = data.get("data", {}).get("sprint_count")
        st.markdown(f"- Burndown JSON: `{burndown}`")
        st.markdown(f"- Sprint Count: `{sprint_count}`")
        if burndown:
            try:
                with open(burndown, "r", encoding="utf-8") as f:
                    bd = json.load(f)
                points = bd.get("burndown", [])
                # aggregate by day index for plotting
                by_day = {}
                for p in points:
                    d = p.get("day", 0)
                    rem = p.get("remaining_sp",0)
                    by_day.setdefault(d, 0)
                    # if multiple sprints, keep min (simulate)
                    if by_day[d] == 0:
                        by_day[d] = rem
                    else:
                        by_day[d] = min(by_day[d], rem)
                xs = sorted(by_day.keys())
                ys = [by_day[x] for x in xs]
                plt.figure(figsize=(7,3))
                plt.plot(xs, ys)
                plt.title("Sprint Burndown (remaining SP by day)")
                plt.xlabel("Day")
                plt.ylabel("Remaining SP")
                st.pyplot(plt)
            except Exception as e:
                st.warning("burndown 로드 실패: " + str(e))

    # Show timeline quick preview
    timeline = data.get("data", {}).get("timeline_path")
    if timeline:
        st.markdown(f"Timeline: `{timeline}`")
        try:
            with open(timeline, "r", encoding="utf-8") as f:
                tl = json.load(f)
            st.table([{"id":t.get("id"), "name":t.get("name"), "ES":t.get("ES"), "EF":t.get("EF")} for t in tl.get("tasks",[])])
        except Exception as e:
            st.warning("timeline load fail: " + str(e))
