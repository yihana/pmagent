#app>main
import json
import os
from dotenv import load_dotenv
import requests
import streamlit as st
from components.history import save_review
from components.sidebar import render_sidebar
from utils.state_manager import init_session_state, reset_session_state

# load_dotenv() 후에 추가
load_dotenv()
API_BASE_URL = os.getenv("API_BASE_URL")
print(f"DEBUG - API_BASE_URL: {API_BASE_URL}")  # 디버깅용

# 만약 None이면 기본값 설정
if API_BASE_URL is None:
    API_BASE_URL = "http://localhost:8001/api/v1"
    print(f"DEBUG - Using default API_BASE_URL: {API_BASE_URL}")

class AgentType:
    TR = "TR_AGENT"
    CO = "CO_AGENT"
    FI = "FI_AGENT"


def process_event_data(event_data):

    # 이벤트 종료
    if event_data.get("type") == "end":
        return True

    # 새로운 메세지
    if event_data.get("type") == "update":
        # state 추출
        data = event_data.get("data", {})

        role = data.get("role")
        response = data["response"]
        agenda = data["agenda"]
        messages = data["messages"]
        current_round = data["current_round"]
        max_rounds = data["max_rounds"]
        docs = data.get("docs", {})

        if role == AgentType.TR:
            st.subheader(f"{current_round}/{max_rounds} 라운드")

        message = response

        if role == AgentType.TR:
            avatar = "👵"
        elif role == AgentType.CO:
            avatar = "👴"
        elif role == AgentType.FI:
            avatar = "🧔"

        with st.chat_message(role, avatar=avatar):
            st.markdown(message)

        if role == AgentType.FI:
            st.session_state.app_mode = "results"
            st.session_state.viewing_history = False
            st.session_state.messages = messages
            st.session_state.docs = docs

            # 완료된 재무분석 정보 저장
            save_review(
                agenda,
                max_rounds,
                messages,
                docs,
            )

            # 참고 자료 표시
            if st.session_state.docs:
                render_source_materials()

            if st.button("새 재무분석 시작"):
                reset_session_state()
                st.session_state.app_mode = "input"
                st.rerun()

    return False


def process_streaming_response(response):
    for chunk in response.iter_lines():
        if not chunk:
            continue

        # 'data: ' 접두사 제거
        line = chunk.decode("utf-8")

        # line의 형태는 'data: {"type": "update", "data": {}}'
        if not line.startswith("data: "):
            continue

        data_str = line[6:]  # 'data: ' 부분 제거

        try:
            # JSON 데이터 파싱
            event_data = json.loads(data_str)

            # 이벤트 데이터 처리
            is_complete = process_event_data(event_data)

            if is_complete:
                break

        except json.JSONDecodeError as e:
            st.error(f"JSON 파싱 오류: {e}")


def start_review():

    agenda = st.session_state.ui_agenda
    max_rounds = st.session_state.max_rounds

    enabled_rag = st.session_state.get("ui_enable_rag", False)

    with st.spinner("재무분석이 진행 중입니다... 완료까지 잠시 기다려주세요."):
        # API 요청 데이터
        data = {
            "agenda": agenda,
            "max_rounds": max_rounds,
            "enable_rag": enabled_rag,
        }

        # 포트 충돌 방지를 위해 환경변수 사용
        API_BASE_URL = os.getenv("API_BASE_URL")
        
        try:
            # 스트리밍 API 호출
            response = requests.post(
                f"{API_BASE_URL}/workflow/review/stream",
                json=data,
                stream=True,
                headers={"Content-Type": "application/json"},
            )

            # stream=True로 설정하여 스트리밍 응답 처리
            # iter_lines() 또는 Iter_content()로 청크단위로 Read

            if response.status_code != 200:
                st.error(f"API 오류: {response.status_code} - {response.text}")
                return

            process_streaming_response(response)

        except requests.RequestException as e:
            st.error(f"API 요청 오류: {str(e)}")


# 참고 자료 표시
def render_source_materials():

    with st.expander("사용된 참고 자료 보기"):
        st.subheader("자금 측 참고 자료")
        for i, doc in enumerate(st.session_state.docs.get(AgentType.TR, [])[:3]):
            st.markdown(f"**문서 {i+1}**")
            st.text(doc[:300] + "..." if len(doc) > 300 else doc)
            st.divider()

        st.subheader("경영관리 측 참고 자료")
        for i, doc in enumerate(st.session_state.docs.get(AgentType.CO, [])[:3]):
            st.markdown(f"**문서 {i+1}**")
            st.text(doc[:300] + "..." if len(doc) > 300 else doc)
            st.divider()

        st.subheader("재무회계 측 참고 자료")
        for i, doc in enumerate(st.session_state.docs.get(AgentType.FI, [])[:3]):
            st.markdown(f"**문서 {i+1}**")
            st.text(doc[:300] + "..." if len(doc) > 300 else doc)
            st.divider()


def display_review_results():

    if st.session_state.viewing_history:
        st.info("📚 이전에 저장된 재무분석을 보고 있습니다.")
        agenda = st.session_state.loaded_agenda
    else:
        agenda = st.session_state.ui_agenda

    # 재무분석 주제 표시
    st.header(f"재무분석 주제: {agenda}")

    for message in st.session_state.messages:

        role = message["role"]
        if role not in [
            AgentType.TR,
            AgentType.CO,
            AgentType.FI,
        ]:
            continue

        if message["role"] == AgentType.TR:
            avatar = "👵"
        elif message["role"] == AgentType.CO:
            avatar = "👴"
        elif message["role"] == AgentType.FI:
            avatar = "🧔"
        with st.chat_message(message["role"], avatar=avatar):
            st.markdown(message["content"])

    if role == AgentType.FI:
        st.session_state.review_active = True
        st.session_state.viewing_history = False

    # 참고 자료 표시
    if st.session_state.docs:
        render_source_materials()

    if st.button("새 재무분석 시작"):
        reset_session_state()
        st.session_state.app_mode = "input"
        st.rerun()


def render_ui():
    # 페이지 설정
    st.set_page_config(page_title="AI 재무분석", page_icon="🤖")

    # 제목 및 소개
    st.title("🤖 AI 재무분석 - 멀티 에이전트")
    st.markdown(
        """
        ### 프로젝트 소개
        이 애플리케이션은 3개의 AI 에이전트(자금, 경영관리, 재무회계)가 사용자가 제시한 주제에 대해 검토을 진행합니다.
        각 AI는 서로의 의견을 듣고 보완하며, 마지막에는 재무회계 AI가 검토 결과를 회계기준으로 정리합니다.
        """
    )

    render_sidebar()

    current_mode = st.session_state.app_mode

    if current_mode == "review":
        start_review()
    elif current_mode == "results":
        display_review_results()


if __name__ == "__main__":

    load_dotenv()

    # 세션 상태 초기화
    init_session_state()

    render_ui()
