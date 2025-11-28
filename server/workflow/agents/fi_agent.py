from server.workflow.agents.agent import Agent
from server.workflow.state import AgentType
from typing import Dict, Any


class FiAgent(Agent):

    def __init__(self, k: int = 2, session_id: str = None):
        super().__init__(
            system_prompt="당신은 공정하고 논리적인 재무회계 컨설턴트 입니다. 양측의 주장을 면밀히 검토하고 객관적으로 회계기준을 적용하여 검토내용을 정리해주세요.",
            role=AgentType.FI,
            k=k,
            session_id=session_id,
        )

    def _create_prompt(self, state: Dict[str, Any]) -> str:

        review_summary = self._build_review_summary(state)

        return f"""
            다음은 '{state['agenda']}'에 대한 재무영역 검토입니다. 각 측의 주장을 분석하고 회계기준으로 정리해주세요.
            
            다음은 이 주제와 관련된 객관적인 정보입니다:
                {state.get("context", "")}
                
            검토 내용:
            {review_summary}
            
            위 검토을 분석하여 다음을 포함하는 회계기준을 근거로 정리를 해주세요:
            1. 양측 주장의 핵심 요약
            2. 각 측이 사용한 주요 논리와 증거의 강점과 약점
            3. 전체 검토의 정리
            4. 회계기준 관점에서 개선점 제안
            
            최대 500자 이내로 작성해주세요.
            """

    def _build_review_summary(self, state: Dict[str, Any]) -> str:

        summary = ""

        # 모든 메시지 순회
        for message in state["messages"]:
            role = message["role"]
            content = message["content"]

            # 역할에 따른 표시 이름
            role_name = (
                AgentType.to_korean(role) if hasattr(AgentType, "to_korean") else role
            )

            # 요약에 메시지 추가
            summary += f"\n\n{role_name}: {content}"

        return summary
