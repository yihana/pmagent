import streamlit as st

from typing import Dict, Any

from components.history import render_history_ui


def render_input_form():
    with st.form("review_form", border=False):
        # 재무분석 주제 입력
        st.text_input(
            label="재무분석 주제를 입력하세요:",
            value="원가관리 방식을 Period base posting에서 Event based posting으로 변경해야합니다.",
            key="ui_agenda",
        )

        max_rounds = st.slider("재무분석 라운드 수", min_value=1, max_value=5, value=1)
        st.session_state.max_rounds = max_rounds
        st.form_submit_button(
            "재무분석 시작",
            on_click=lambda: st.session_state.update({"app_mode": "review"}),
        )
        # RAG 기능 활성화 옵션
        st.checkbox(
            "RAG 활성화",
            value=True,
            help="외부 지식을 검색하여 재무분석에 활용합니다.",
            key="ui_enable_rag",
        )


def render_sidebar() -> Dict[str, Any]:
    with st.sidebar:

        tab1, tab2 = st.tabs(["새 재무분석", "재무분석 이력"])

        with tab1:
            render_input_form()

        with tab2:
            render_history_ui()
