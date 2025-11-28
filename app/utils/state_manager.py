import streamlit as st


def init_session_state():
    # 세션 스테이트 초기화
    if "app_mode" not in st.session_state:
        reset_session_state()


def reset_session_state():
    st.session_state.app_mode = False
    st.session_state.round = 0
    st.session_state.viewing_history = False
    st.session_state.loaded_review_id = None
    st.session_state.docs = {}


def set_review_to_state(agenda, messages, review_id, docs):
    st.session_state.app_mode = True
    st.session_state.messages = messages
    st.session_state.viewing_history = True
    st.session_state.review_agenda = agenda
    st.session_state.loaded_review_id = review_id
    st.session_state.docs = docs
