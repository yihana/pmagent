import streamlit as st
from utils.config import get_llm

try:
    # ✅ 최신 버전 (LangChain 0.1.x 이상)
    from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
except ImportError:
    # ✅ 구버전 호환
    from langchain.schema import HumanMessage, SystemMessage, AIMessage

# AI 응답 생성 함수 (메시지 히스토리 포함)
def generate_response(prompt, system_prompt, message_history=None):
    messages = [SystemMessage(content=system_prompt)]

    # 메시지 히스토리가 있으면 추가
    if message_history:
        for message in message_history:
            if message["role"] == "assistant":
                messages.append(AIMessage(content=message["content"]))
            else:
                messages.append(
                    HumanMessage(content=f"{message['role']}: {message['content']}")
                )

    # 현재 프롬프트 추가
    messages.append(HumanMessage(content=prompt))

    # LLM 호출
    response = get_llm().invoke(messages)
    return response.content


# 검토 단계별 기능을 함수로 분리
def handle_tr_round(agenda: str):
    with st.spinner("자금관리 측 의견을 생성 중입니다..."):

        if st.session_state.round == 1:
            # 첫 번째 자금 측 의견 생성
            tr_prompt = f"""
            당신은 '{agenda}'에 대해 자금관리 컨설턴트 입장을 가진 토론자입니다.
            논리적이고 설득력 있는 자금관리 측 주장을 제시해주세요.
            200자 내로 작성해주세요.
            """
            system_prompt = "당신은 논리적이고 설득력 있는 자금관리 컨설턴트 측 토론자입니다."
        else:
            # 이전 경영관리 측 의견에 대한 보완
            previous_argument = st.session_state.messages[-1]["content"]
            tr_prompt = f"""
            당신은 '{agenda}'에 대해 자금관리 컨설턴트 입장을 가진 토론자입니다.
            경영관리 측의 다음 주장에 대해 검토하고, 자금관리 입장을 더 강화해주세요:

            경영관리 측 주장: "{previous_argument}"

            200자 내로 작성해주세요.
            """
            system_prompt = "당신은 논리적이고 설득력 있는 자금관리 컨설턴트 입니다. 경영관리 측 주장에 대해 적극적으로 보완하세요."

        tr_argument = generate_response(
            tr_prompt, system_prompt, st.session_state.messages
        )

        st.session_state.messages.append({"role": "자금 측", "content": tr_argument})


def handle_co_round(agenda: str):
    with st.spinner("경영관리 측 의견을 생성 중입니다..."):
        previous_argument = st.session_state.messages[-1]["content"]
        co_prompt = f"""
        당신은 '{agenda}'에 대해 경영관리 입장을 가진 컨설턴트 입니다.
        자금 측의 다음 주장에 대해 검토하고, 경영관리 입장을 제시해주세요:

        자금 측 주장: "{previous_argument}"

        200자 내로 작성해주세요.
        """
        system_prompt = "당신은 논리적이고 설득력 있는 경영관리 측 토론자입니다. 자금 측 주장에 대해 적극적으로 검토하세요."

        co_argument = generate_response(
            co_prompt, system_prompt, st.session_state.messages
        )

        st.session_state.messages.append({"role": "경영관리 측", "content": co_argument})


def handle_fi(agenda: str):
    with st.spinner("재무회계 컨설턴트가 회계기준으로 정리 중입니다..."):
        fi_prompt = f"""
        다음은 '{agenda}'에 대한 검토입니다. 각 측의 검토내용을 회계기준에서 분석하고 종합해주세요.

        검토 내용:
        """
        for entry in st.session_state.messages:
            fi_prompt += f"\n\n{entry['role']}: {entry['content']}"

        fi_prompt += """
        
        위 토론을 분석하여 다음을 포함하는 정리를 해주세요:
        1. 양측 주장의 핵심 요약
        2. 각 측이 사용한 주요 논리와 증거의 강점과 약점
        3. 전체 재무관점 검토 의견
        4. 회계기준 기반 제안
        """
        system_prompt = "당신은 공정하고 논리적인 재무회계 컨설턴트 입니다. 주제를 검토하고 객관적으로 정리해주세요."

        fi_argument = generate_response(fi_prompt, system_prompt, [])

        st.session_state.messages.append({"role": "재무회계", "content": fi_argument})
