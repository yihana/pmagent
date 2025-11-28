import streamlit as st

from review import handle_con_round, handle_judge, handle_pro_round
from utils.state_manager import init_session_state, reset_session_state


def render_input_form():
    with st.form("review_form", border=False):
        # 주제 입력
        st.text_input(
            label="주제를 입력하세요:",
            value="예산을 변경합니다.",
            key="ui_agenda",
        )

        max_rounds = st.slider("라운드 수", min_value=1, max_value=5, value=1)
        st.session_state.max_rounds = max_rounds
        st.form_submit_button(
            "시작",
            on_click=lambda: st.session_state.update({"app_mode": "review"}),
        )


def start_review():

    agenda = st.session_state.ui_agenda
    max_rounds = st.session_state.max_rounds

    st.header(f"주제: {agenda}")

    total_steps = max_rounds * 2 + 1  # 각 라운드의 자금, 경영관리 + 최종 재무회계
    current_step = 0
    progress_bar = st.progress(0)

    for i in range(max_rounds):
        handle_pro_round(agenda)
        current_step += 1
        progress_bar.progress(current_step / total_steps)
        handle_con_round(agenda)
        current_step += 1
        progress_bar.progress(current_step / total_steps)

    handle_judge(agenda)
    current_step += 1
    progress_bar.progress(current_step / total_steps)

    # 결과 모드로 전환
    st.session_state.app_mode = "results"
    st.rerun()


def display_review_results():
    # 내용 표시
    st.header("진행 상황")
    for i, entry in enumerate(st.session_state.messages):
        round_num = (i // 2) + 1

        if round_num <= st.session_state.max_rounds:
            if i % 2 == 0:
                st.subheader(f"라운드 {round_num} / {st.session_state.max_rounds}")
            st.subheader(entry["role"])
        else:
            st.header("재무회계")
        st.write(entry["content"])
        st.divider()

    if st.button("다시 시작"):
        reset_session_state()
        st.session_state.app_mode = "input"
        st.rerun()


def render_ui():
    # 페이지 설정
    st.set_page_config(page_title="AI 검토", page_icon="🤖")

    # 제목 및 소개
    st.title("🤖 AI 재무검토 - 멀티 에이전트")
    st.markdown(
        """
        ### 프로젝트 소개
        이 애플리케이션은 3개의 AI 에이전트(FI, CO, TR)가 사용자가 제시한 주제에 대해 회의를 진행합니다.
        각 AI는 서로의 의견을 듣고 전문가적인 의견은 제안하며, 마지막에는 FI AI가 회계적으로 정리합니다.
        """
    )

    render_input_form()

    current_mode = st.session_state.get("app_mode")

    if current_mode == "review":
        start_review()
    if current_mode == "results":
        display_review_results()


if __name__ == "__main__":
    # 세션 상태 초기화
    init_session_state()

    # 앱 모드가 없으면 입력 모드로 설정
    if "app_mode" not in st.session_state:
        st.session_state.app_mode = "input"

    render_ui()
