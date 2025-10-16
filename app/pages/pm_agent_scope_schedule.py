# app/pages/pm_agent_scope_schedule.py
import os
import io
import json
import requests
import streamlit as st
from dotenv import load_dotenv
from urllib.parse import urljoin, urlparse

load_dotenv()

def get_api_base() -> str:
    v = os.getenv("API_BASE_URL") or "http://127.0.0.1:8001/api/"
    if not urlparse(v).scheme:
        v = "http://" + v
    if not v.endswith("/"):
        v += "/"
    return v

API_BASE = get_api_base()
SCOPE_URL = urljoin(API_BASE, "scope/run")
SCHEDULE_URL = urljoin(API_BASE, "schedule/run")
WORKFLOW_URL = urljoin(API_BASE, "workflow/scope-then-schedule")

st.set_page_config(page_title="PM Agent - Scope & Schedule", layout="wide")
st.title("🧭 PM Agent — Scope & Schedule")

with st.sidebar:
    st.header("설정")
    api_input = st.text_input("API Base URL", API_BASE, help="예) http://127.0.0.1:8001/api/")
    if api_input and api_input != API_BASE:
        API_BASE = api_input if api_input.endswith("/") else api_input + "/"
        SCOPE_URL = urljoin(API_BASE, "scope/run")
        SCHEDULE_URL = urljoin(API_BASE, "schedule/run")
        WORKFLOW_URL = urljoin(API_BASE, "workflow/scope-then-schedule")
    st.markdown("---")
    st.caption("주의: 서버에 업로드된 RFP 파일 경로를 사용하거나\n서버경로로 복사 후 경로 입력하세요.")

# --- Input: Project / Methodology ---
st.markdown("### 프로젝트 & 방법론 설정")
col1, col2, col3 = st.columns([2,2,1])
with col1:
    project_name = st.text_input("프로젝트명", "Demo Project")
with col2:
    methodology = st.selectbox("방법론", ["waterfall", "agile"], index=0)
with col3:
    chunk_size = st.number_input("Chunk size", value=500, step=50)
    overlap = st.number_input("Overlap", value=100, step=10)

st.markdown("### RFP 입력 (2가지 모드)")
mode = st.radio("파일입력 모드 선택", ["서버 경로 입력 (권장)", "파일 업로드 (로컬 → 서버 미지원: 안내용)"])

server_file_path = None
if mode == "서버 경로 입력 (권장)":
    st.markdown("**서버에 이미 올려진 RFP 파일 경로** 를 입력하세요. (예: `data/inputs/RFP/sample_rfp.pdf`)\n\n서버와 동일 환경에서 Streamlit을 돌리는 경우 상대경로로 지정하면 됩니다.")
    server_file_path = st.text_input("서버 파일 경로", "data/inputs/RFP/sample_rfp.pdf")
else:
    st.markdown("로컬 파일 업로드 버튼(로컬 업로드는 백엔드에 업로드 엔드포인트가 없으면 동작하지 않습니다).")
    upload = st.file_uploader("RFP PDF 업로드 (테스트용)", type=["pdf"])
    if upload is not None:
        # save to a temp file path on Streamlit server (only works if Streamlit runs where server can access)
        tmp_dir = os.getenv("STREAMLIT_UPLOAD_DIR", "data/inputs/RFP")
        os.makedirs(tmp_dir, exist_ok=True)
        dest_path = os.path.join(tmp_dir, upload.name)
        with open(dest_path, "wb") as f:
            f.write(upload.getbuffer())
        st.success(f"로컬 파일을 서버 경로로 저장했습니다: {dest_path}")
        server_file_path = dest_path

st.markdown("---")

# --- Buttons: Scope / Schedule / Workflow ---
colA, colB, colC = st.columns(3)

def _show_response_json(resp):
    try:
        data = resp.json()
        st.write("### 응답(JSON)")
        st.json(data)
        return data
    except Exception:
        st.text(resp.text)
        return None

# Scope
with colA:
    if st.button("🔎 Scope 추출 실행"):
        if not server_file_path or not server_file_path.strip():
            st.error("서버 파일 경로를 입력하거나 업로드 해주세요.")
        else:
            payload = {
                "project_name": project_name,
                "methodology": methodology,
                "documents": [{"path": server_file_path, "type": "RFP"}],
                "options": {"chunk_size": int(chunk_size), "overlap": int(overlap)}
            }
            st.info(f"요청: {SCOPE_URL}")
            with st.spinner("Scope Agent 실행 중..."):
                try:
                    res = requests.post(SCOPE_URL, json=payload, timeout=180)
                    if res.status_code == 200:
                        st.success("✅ Scope 생성 완료")
                        data = _show_response_json(res)
                        if data:
                            st.markdown("**생성된 파일**")
                            st.write(f"- Scope Statement: `{data.get('scope_statement_md')}`")
                            st.write(f"- RTM: `{data.get('rtm_csv')}`")
                            st.write(f"- WBS JSON: `{data.get('wbs_json')}`")
                    else:
                        st.error(f"Scope API 오류: {res.status_code}")
                        st.text(res.text)
                except Exception as e:
                    st.error(f"요청 실패: {e}")

# Schedule
with colB:
    wbs_path_input = st.text_input("Schedule 입력 WBS JSON 경로 (서버)", value="data/outputs/scope/wbs_structure.json")
    calendar_start = st.date_input("시작일", value=None)
    holidays_raw = st.text_input("휴일 (콤마로 구분, YYYY-MM-DD 형식)", value="")
    sprint_len = st.number_input("Sprint 길이(주)", min_value=1, value=2)

    if st.button("🗓️ Schedule 생성 실행"):
        if not os.path.exists(wbs_path_input) and not wbs_path_input.startswith("/"):
            # still allow user to call; the backend will fail if path invalid
            st.warning("입력한 WBS 경로가 현재 Streamlit 서버 경로에 없습니다. 서버에 해당 파일이 있는지 확인하세요.")
        calendar = {
            "start_date": calendar_start.isoformat() if calendar_start else "2025-11-03",
            "work_week": [1,2,3,4,5],
            "holidays": [h.strip() for h in holidays_raw.split(",") if h.strip()]
        }
        payload = {
            "wbs_json": wbs_path_input,
            "calendar": calendar,
            "resource_pool": [{"role":"PM","capacity_pct":80}],
            "sprint_length_weeks": int(sprint_len),
            "estimation_mode": "llm",
            "methodology": methodology
        }
        st.info(f"요청: {SCHEDULE_URL}")
        with st.spinner("Schedule Agent 실행 중..."):
            try:
                res = requests.post(SCHEDULE_URL, json=payload, timeout=180)
                if res.status_code == 200:
                    st.success("✅ Schedule 생성 완료")
                    data = _show_response_json(res)
                    if data:
                        st.markdown("**생성된 파일**")
                        st.write(f"- Schedule CSV: `{data.get('plan_csv')}`")
                        st.write(f"- Gantt JSON: `{data.get('gantt_json')}`")
                        st.write(f"- Critical Path: `{data.get('critical_path')}`")
                else:
                    st.error(f"Schedule API 오류: {res.status_code}")
                    st.text(res.text)
            except Exception as e:
                st.error(f"요청 실패: {e}")

# Workflow (Scope -> Schedule)
with colC:
    if st.button("🔁 전체 워크플로우 실행 (Scope -> Schedule)"):
        if not server_file_path or not server_file_path.strip():
            st.error("서버 파일 경로를 입력하거나 업로드 해주세요.")
        else:
            scope_payload = {
                "project_name": project_name,
                "methodology": methodology,
                "documents": [{"path": server_file_path, "type": "RFP"}],
                "options": {"chunk_size": int(chunk_size), "overlap": int(overlap)}
            }
            workflow_payload = {
                "scope": scope_payload,
                "schedule": {
                    "methodology": methodology,
                    "calendar": {"start_date": st.session_state.get("workflow_start", None) or "2025-11-03", "work_week":[1,2,3,4,5], "holidays":[]},
                    "sprint_length_weeks": int(sprint_len)
                }
            }
            st.info(f"요청: {WORKFLOW_URL}")
            with st.spinner("워크플로우 실행 중..."):
                try:
                    res = requests.post(WORKFLOW_URL, json=workflow_payload, timeout=300)
                    if res.status_code == 200:
                        st.success("✅ 워크플로우 완료")
                        data = _show_response_json(res)
                        if data:
                            st.markdown("**Scope / Schedule 생성 결과**")
                            st.write(data)
                    else:
                        st.error(f"Workflow API 오류: {res.status_code}")
                        st.text(res.text)
                except Exception as e:
                    st.error(f"요청 실패: {e}")

st.markdown("---")
st.caption("Tip: 서버 경로로 파일이 없다면, 서버 터미널에서 RFP 파일을 data/inputs/RFP/ 에 복사한 뒤 경로를 입력하세요.")
