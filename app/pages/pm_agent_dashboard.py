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
    api_base = st.text_input("API Base URL", API_BASE, help="예) http://127.0.0.1:8001/api/v1")
    if api_base != API_BASE:
        API_BASE = api_base if api_base.endswith("/") else api_base + "/"
        PM_ANALYZE_URL = urljoin(API_BASE, "pm/graph/analyze")
        PM_REPORT_URL  = urljoin(API_BASE, "pm/graph/report")

# ============================================
# 3. 입력 영역 (프로젝트 정보)
# ============================================
st.markdown("### 🔧 프로젝트 입력")
col1, col2, col3 = st.columns(3)
with col1:
    project_id_str = st.text_input("프로젝트 ID", "1001")
with col2:
    doc_type = st.selectbox("문서 유형", ["meeting", "report", "issue"])
with col3:
    title = st.text_input("문서 제목", "PM 주간 회의록")

text_input = st.text_area("분석할 문서 내용 입력", height=250, placeholder="회의 요약이나 주요 이슈 내용을 여기에 입력하세요.")

# ============================================
# 3-1. 리포트 조회 옵션 (기간/고급)
# ============================================
with st.expander("📅 리포트 조회 옵션 (선택)"):
    r1, r2, r3 = st.columns(3)
    with r1:
        start_date = st.date_input("Start date", value=None, format="YYYY-MM-DD")
    with r2:
        end_date = st.date_input("End date", value=None, format="YYYY-MM-DD")
    with r3:
        fast = st.checkbox("Fast Mode", value=True, help="백엔드가 지원하는 경우 요약만 빠르게 가져옵니다.")
    r4, r5 = st.columns(2)
    with r4:
        include_json = st.checkbox("원본 JSON 포함", value=False)
    with r5:
        limit = st.number_input("섹션별 최대 개수 (선택)", min_value=0, value=0, help="0이면 제한 없음")

# ============================================
# 4. 버튼 액션
# ============================================
col_a, col_b = st.columns([1, 1])

def _safe_project_id(pid_str: str) -> int | None:
    try:
        return int(pid_str.strip())
    except Exception:
        return None

with col_a:
    if st.button("📥 인제스트 → 분석 실행"):
        if not text_input.strip():
            st.warning("분석할 텍스트를 입력해주세요.")
        else:
            pid = _safe_project_id(project_id_str)
            if pid is None:
                st.error("프로젝트 ID는 숫자여야 합니다.")
            else:
                with st.spinner("분석 중... 잠시만 기다려주세요 ⏳"):
                    payload = {
                        "project_id": pid,
                        "doc_type": doc_type,
                        "title": title,
                        "text": text_input,
                    }
                    try:
                        res = requests.post(PM_ANALYZE_URL, json=payload, timeout=180)
                        if res.status_code == 200:
                            st.success("✅ 분석 완료!")
                            result = res.json()
                            # 결과 원본
                            st.subheader("분석 결과 (원본 JSON)")
                            st.json(result)
                        else:
                            st.error(f"API 오류: {res.status_code}")
                            st.text(res.text)
                    except Exception as e:
                        st.error(f"요청 실패: {e}")

with col_b:
    if st.button("📊 분석 리포트 조회"):
        pid = _safe_project_id(project_id_str)
        if pid is None:
            st.error("프로젝트 ID는 숫자여야 합니다.")
        else:
            params: dict[str, object] = {"project_id": pid}
            if start_date:
                params["start_date"] = start_date.isoformat()
            if end_date:
                params["end_date"] = end_date.isoformat()
            if fast is not None:
                params["fast"] = str(bool(fast)).lower()  # true/false 문자열로 전달
            if include_json:
                params["include_json"] = "true"
            if limit and int(limit) > 0:
                params["limit"] = int(limit)

            try:
                res = requests.get(PM_REPORT_URL, params=params, timeout=60)
                if res.status_code == 200:
                    data = res.json()
                    st.success("📑 리포트 조회 성공")

                    # 1) 마크다운 요약이 있으면 보기 좋게 렌더링
                    summary_md = data.get("summary_md") or data.get("summary") or ""
                    if summary_md:
                        st.subheader("리포트 요약 (Markdown)")
                        st.markdown(summary_md)

                    # 2) 통계/원본 JSON도 함께 표시
                    st.subheader("리포트 응답 (원본 JSON)")
                    st.json(data)
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
