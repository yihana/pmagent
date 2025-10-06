# app/pages/pm_agent_dashboard.py
import os
import requests
import streamlit as st
from dotenv import load_dotenv
from urllib.parse import urljoin, urlparse

# ============================================
# 1. 환경 변수 로드 및 API_BASE 설정
# ============================================
load_dotenv()

def get_api_base() -> str:
    """API Base URL을 안전하게 반환"""
    v = os.getenv("API_BASE_URL") or "http://127.0.0.1:8001/api/v1"
    if not urlparse(v).scheme:
        v = "http://" + v
    if not v.endswith("/"):
        v += "/"
    return v

API_BASE = get_api_base()
PM_ANALYZE_URL = urljoin(API_BASE, "pm/graph/analyze")
PM_REPORT_URL  = urljoin(API_BASE, "pm/graph/report")

# ============================================
# 2. Streamlit 페이지 설정
# ============================================
st.set_page_config(page_title="PM Agent Dashboard", layout="wide")
st.title("📊 PM Agent Dashboard")

with st.sidebar:
    st.subheader("설정")
    api_base = st.text_input("API Base URL", API_BASE)
    if api_base != API_BASE:
        API_BASE = api_base
        PM_ANALYZE_URL = urljoin(API_BASE, "pm/graph/analyze")
        PM_REPORT_URL  = urljoin(API_BASE, "pm/graph/report")

# ============================================
# 3. 입력 영역 (프로젝트 정보)
# ============================================
st.markdown("### 🔧 프로젝트 입력")
col1, col2, col3 = st.columns(3)
with col1:
    project_id = st.text_input("프로젝트 ID", "1001")
with col2:
    doc_type = st.selectbox("문서 유형", ["meeting", "report", "issue"])
with col3:
    title = st.text_input("문서 제목", "PM 주간 회의록")

text_input = st.text_area("분석할 문서 내용 입력", height=250, placeholder="회의 요약이나 주요 이슈 내용을 여기에 입력하세요.")

# ============================================
# 4. 버튼 액션
# ============================================
col_a, col_b = st.columns([1, 1])

with col_a:
    if st.button("📥 인제스트 → 분석 실행"):
        if not text_input.strip():
            st.warning("분석할 텍스트를 입력해주세요.")
        else:
            with st.spinner("분석 중... 잠시만 기다려주세요 ⏳"):
                payload = {
                    "project_id": project_id,
                    "doc_type": doc_type,
                    "title": title,
                    "text": text_input,
                }
                try:
                    res = requests.post(PM_ANALYZE_URL, json=payload, timeout=180)
                    if res.status_code == 200:
                        st.success("✅ 분석 완료!")
                        result = res.json()
                        st.json(result)
                    else:
                        st.error(f"API 오류: {res.status_code}")
                        st.text(res.text)
                except Exception as e:
                    st.error(f"요청 실패: {e}")

with col_b:
    if st.button("📊 분석 리포트 조회"):
        try:
            res = requests.get(PM_REPORT_URL, params={"project_id": project_id}, timeout=60)
            if res.status_code == 200:
                st.success("📑 리포트 조회 성공")
                st.json(res.json())
            else:
                st.error(f"리포트 API 오류: {res.status_code}")
                st.text(res.text)
        except Exception as e:
            st.error(f"리포트 요청 실패: {e}")

# ============================================
# 5. Debug Info
# ============================================
st.markdown("---")
st.caption("🔍 Debug Info")
st.code(f"""
API_BASE = {API_BASE}
PM_ANALYZE_URL = {PM_ANALYZE_URL}
PM_REPORT_URL = {PM_REPORT_URL}
""", language="python")
