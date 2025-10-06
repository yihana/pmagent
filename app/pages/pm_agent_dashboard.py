import os
import streamlit as st, requests, pandas as pd
import datetime as dt


def _get_api_base():
    try:
        # secrets가 있으면 사용
        return st.secrets["API_BASE_URL"]
    except Exception:
        # 없으면 환경변수 -> 기본값
        return os.getenv("API_BASE_URL", "http://localhost:8001/api/v1")

API = _get_api_base()
API_BASE_URL = API

st.write(f"DEBUG - API_BASE_URL: {API}")

st.title("PM Agent Dashboard")

st.subheader("문서 업로드 & 분석")
col1, col2 = st.columns([1,3])
with col1:
    project_id = st.number_input("Project ID", value=1, step=1)
    doc_type = st.selectbox("문서 유형", ["meeting","rfp","proposal","issue"])
    title = st.text_input("제목", value=f"{doc_type} - {dt.date.today()}")
with col2:
    content = st.text_area("내용(붙여넣기)", height=220)

if st.button("인제스트 → 분석"):
    r = requests.post(f"{API}/pm/documents/ingest", json={
        "project_id": project_id, "doc_type": doc_type, "title": title, "content": content
    })
    if r.ok:
        doc_id = r.json()["document_id"]
        r2 = requests.post(f"{API}/pm/documents/analyze", json={"project_id": project_id, "document_id": doc_id})
        st.success("분석 완료")
        st.json(r2.json())
    else:
        st.error(r.text)

st.divider()
st.subheader("Weekly Report & ROI")
c1, c2, c3 = st.columns(3)
with c1:
    start = st.date_input("Week Start", value=dt.date.today() - dt.timedelta(days=7))
with c2:
    end = st.date_input("Week End", value=dt.date.today())

if st.button("Generate Weekly Report"):
    r = requests.get(f"{API}/pm/report/weekly", params={
        "project_id": project_id, "week_start": str(start), "week_end": str(end)
    })
    if r.ok:
        res = r.json()
        st.markdown(res["summary_md"])
    else:
        st.error(r.text)

st.info("경영진용 보고서 Export(docx/pdf)은 추후 버튼 추가 예정 (python-docx/reportlab 연동)")
