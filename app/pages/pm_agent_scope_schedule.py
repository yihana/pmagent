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
    """API Base URL을 환경변수 또는 기본값에서 가져옴"""
    v = os.getenv("API_BASE_URL") or "http://127.0.0.1:8001"
    if not urlparse(v).scheme:
        v = "http://" + v
    # 끝의 / 제거
    v = v.rstrip("/")
    # /api 또는 /api/v1이 이미 포함되어 있다면 제거
    if v.endswith("/api/v1"):
        v = v[:-7]
    elif v.endswith("/api"):
        v = v[:-4]
    return v

API_BASE = get_api_base()
# pm_work.py의 라우터 prefix가 /api/v1/pm이므로 전체 경로 명시
SCOPE_URL = f"{API_BASE}/api/v1/pm/scope/analyze"
SCHEDULE_URL = f"{API_BASE}/api/v1/pm/schedule/analyze"
WORKFLOW_URL = f"{API_BASE}/api/v1/pm/workflow/scope-then-schedule"
UPLOAD_URL = f"{API_BASE}/api/v1/pm/upload/rfp"

st.set_page_config(page_title="PM Agent - Scope & Schedule", layout="wide")
st.title("🧭 PM Agent — Scope & Schedule")

with st.sidebar:
    st.header("설정")
    api_input = st.text_input(
        "API Base URL", 
        API_BASE, 
        help="서버 주소만 입력하세요. 예) http://127.0.0.1:8001"
    )
    if api_input and api_input != API_BASE:
        # 입력값 정규화
        api_input = api_input.rstrip("/")
        if api_input.endswith("/api/v1"):
            api_input = api_input[:-7]
        elif api_input.endswith("/api"):
            api_input = api_input[:-4]
        
        API_BASE = api_input
        SCOPE_URL = f"{API_BASE}/api/v1/pm/scope/analyze"
        SCHEDULE_URL = f"{API_BASE}/api/v1/pm/schedule/analyze"
        WORKFLOW_URL = f"{API_BASE}/api/v1/pm/workflow/scope-then-schedule"
        UPLOAD_URL = f"{API_BASE}/api/v1/pm/upload/rfp"
    
    st.markdown("---")
    st.success(f"🔗 서버: {API_BASE}")
    with st.expander("📋 API 엔드포인트 확인"):
        st.code(f"Upload:   {UPLOAD_URL}", language="text")
        st.code(f"Scope:    {SCOPE_URL}", language="text")
        st.code(f"Schedule: {SCHEDULE_URL}", language="text")
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
mode = st.radio("파일입력 모드 선택", ["서버 경로 입력 (권장)", "파일 업로드 (로컬 → 서버)"])

server_file_path = None

if mode == "서버 경로 입력 (권장)":
    st.markdown("**서버에 이미 올려진 RFP 파일 경로** 를 입력하세요.")
    st.caption("예: `data/inputs/RFP/sample_rfp.pdf` 또는 `D:/workspace/pm-agent/data/inputs/RFP/sample_rfp.pdf`")
    
    # 기본값을 세션에서 가져오기
    default_path = st.session_state.get("uploaded_rfp_path", "data/inputs/RFP/sample_rfp.pdf")
    server_file_path = st.text_input("서버 파일 경로", default_path)
    
    # Windows 절대경로 → 상대경로 변환 도우미
    if server_file_path and ":" in server_file_path:  # Windows 절대경로인 경우
        try:
            from pathlib import Path
            abs_path = Path(server_file_path)
            # D:\workspace\pm-agent\data\... → data/...
            if "data" in str(abs_path):
                rel_path = str(abs_path).split("data")[-1].lstrip("\\/")
                rel_path = f"data/{rel_path}".replace("\\", "/")
                st.info(f"💡 변환된 상대경로: `{rel_path}`")
                if st.button("📝 상대경로로 자동 입력"):
                    st.session_state["uploaded_rfp_path"] = rel_path
                    st.rerun()
        except:
            pass
            
else:
    st.markdown("**로컬 파일을 서버로 업로드합니다**")
    upload = st.file_uploader("RFP PDF 업로드", type=["pdf"])
    
    if upload is not None:
        st.info(f"📄 선택된 파일: {upload.name} ({upload.size:,} bytes)")
        
        col_up1, col_up2 = st.columns([1, 2])
        with col_up1:
            if st.button("🔼 서버로 업로드"):
                with st.spinner("파일 업로드 중..."):
                    try:
                        files = {"file": (upload.name, upload.getvalue(), "application/pdf")}
                        st.write(f"🔗 요청 URL: {UPLOAD_URL}")
                        res = requests.post(UPLOAD_URL, files=files, timeout=60)
                        
                        if res.status_code == 200:
                            data = res.json()
                            server_file_path = data.get("path")
                            st.success(f"✅ 업로드 완료!")
                            st.session_state["uploaded_rfp_path"] = server_file_path
                            st.rerun()
                        else:
                            st.error(f"❌ 업로드 실패: {res.status_code}")
                            st.text(res.text)
                            st.warning("💡 임시 해결: 파일을 수동으로 `data/inputs/RFP/` 폴더에 복사한 후 '서버 경로 입력' 모드를 사용하세요.")
                    except Exception as e:
                        st.error(f"업로드 오류: {e}")
                        import traceback
                        st.code(traceback.format_exc())
        
        with col_up2:
            # 수동 경로 입력 옵션
            manual_path = f"data/inputs/RFP/{upload.name}"
            st.caption(f"💡 또는 파일을 서버의 `{manual_path}` 경로에 수동 복사 후 아래 버튼 클릭")
            if st.button("📁 수동 복사 완료 (경로 저장)"):
                st.session_state["uploaded_rfp_path"] = manual_path
                st.success(f"✅ 경로 저장: {manual_path}")
                st.rerun()
        
        # 이미 업로드된 경로가 있으면 사용
        if "uploaded_rfp_path" in st.session_state:
            server_file_path = st.session_state["uploaded_rfp_path"]
            st.success(f"✅ 사용할 파일 경로: `{server_file_path}`")

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
            st.json(payload)
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
                            wbs_path = data.get('wbs_json')
                            st.write(f"- WBS JSON: `{wbs_path}`")
                            
                            # WBS 경로를 세션에 저장 (Schedule에서 사용)
                            if wbs_path:
                                st.session_state["wbs_json_path"] = wbs_path
                                st.success(f"✅ WBS 경로가 저장되었습니다: {wbs_path}")
                    else:
                        st.error(f"Scope API 오류: {res.status_code}")
                        st.text(res.text)
                except Exception as e:
                    st.error(f"요청 실패: {e}")
                    import traceback
                    st.code(traceback.format_exc())

# Schedule
with colB:
    # WBS 경로 자동 채우기
    default_wbs = st.session_state.get("wbs_json_path", "data/outputs/scope/wbs_structure.json")
    wbs_path_input = st.text_input("Schedule 입력 WBS JSON 경로 (서버)", value=default_wbs)
    
    calendar_start = st.date_input("시작일", value=None)
    holidays_raw = st.text_input("휴일 (콤마로 구분, YYYY-MM-DD 형식)", value="")
    sprint_len = st.number_input("Sprint 길이(주)", min_value=1, value=2)

    if st.button("🗓️ Schedule 생성 실행"):
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
    workflow_start = st.date_input("Workflow 시작일", value=None, key="workflow_date")
    
    if st.button("🔄 전체 워크플로우 실행 (Scope -> Schedule)"):
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
                    "calendar": {
                        "start_date": workflow_start.isoformat() if workflow_start else "2025-11-03",
                        "work_week": [1,2,3,4,5],
                        "holidays": []
                    },
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
                            if data.get("scope"):
                                st.write("**Scope 결과:**")
                                st.json(data["scope"])
                            if data.get("schedule"):
                                st.write("**Schedule 결과:**")
                                st.json(data["schedule"])
                    else:
                        st.error(f"Workflow API 오류: {res.status_code}")
                        st.text(res.text)
                except Exception as e:
                    st.error(f"요청 실패: {e}")

st.markdown("---")
st.caption("Tip: 로컬 파일을 업로드하면 서버의 data/inputs/RFP/ 경로에 저장됩니다.")