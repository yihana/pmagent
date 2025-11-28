from server.workflow.agents.agent import Agent
from server.workflow.state import AgentType
from typing import Dict, Any


class TrAgent(Agent):

    def __init__(self, k: int = 2, session_id: str = None):
        super().__init__(
            system_prompt="당신은 논리적이고 설득력 있는 자금 컨설턴트 입니다.",
            role=AgentType.TR,
            k=k,
            session_id=session_id,
        )

    def _create_prompt(self, state: Dict[str, Any]) -> str:
        if state["current_round"] == 1:
            return self._create_first_round_prompt(state)
        else:
            return self._create_rebuttal_prompt(state)

    def _create_first_round_prompt(self, state: Dict[str, Any]) -> str:
        return f"""
            당신은 '{state['agenda']}'에 대해 자금 컨설턴트 입장 검토자입니다.
            다음은 이 주제와 관련된 정보입니다:
                {state.get("context", "")}
            논리적이고 설득력 있는 자금관리 측 주장을 제시해주세요.
            가능한 경우 제공된 정보에서 구체적인 근거를 인용하세요.
            2 ~ 3문단, 각 문단은 100자내로 작성해주세요.
            """

    def _create_rebuttal_prompt(self, state: Dict[str, Any]) -> str:
        # 이전 발언자의 마지막 메시지를 가져옴
        previous_messages = [m for m in state["messages"] if m["role"] == AgentType.CO]
        last_co_message = previous_messages[-1]["content"] if previous_messages else ""

        return f"""
            당신은 '{state['agenda']}'에 대해 자금 컨설턴트 입장 검토자입니다.
            다음은 이 주제와 관련된 정보입니다:
                {state.get("context", "")}
            경영관리 측의 다음 주장에 대해 보완하고, 자금관리 입장을 더 강화해주세요:
            경영관리 측 주장: "{last_co_message}"

            2 ~ 3문단, 각 문단은 100자내로 작성해주세요.
            """
