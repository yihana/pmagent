from server.workflow.agents.co_agent import CoAgent
from server.workflow.agents.fi_agent import FiAgent
from server.workflow.agents.tr_agent import TrAgent
from server.workflow.agents.round_manager import RoundManager
from server.workflow.state import ReviewState, AgentType
from langgraph.graph import StateGraph, END


def create_review_graph(enable_rag: bool = True, session_id: str = ""):

    # 그래프 생성
    workflow = StateGraph(ReviewState)

    # 에이전트 인스턴스 생성 - enable_rag에 따라 검색 문서 수 결정
    k_value = 2 if enable_rag else 0
    TR_AGENT = TrAgent(k=k_value, session_id=session_id)
    CO_AGENT = CoAgent(k=k_value, session_id=session_id)
    FI_AGENT = FiAgent(k=k_value, session_id=session_id)
    round_manager = RoundManager()

    # 노드 추가
    workflow.add_node(AgentType.TR, TR_AGENT.run)
    workflow.add_node(AgentType.CO, CO_AGENT.run)
    workflow.add_node(AgentType.FI, FI_AGENT.run)
    workflow.add_node("INCREMENT_ROUND", round_manager.run)
    workflow.add_edge(AgentType.TR, AgentType.CO)  # 자금관리 조건부 라우팅
    workflow.add_edge(AgentType.CO, "INCREMENT_ROUND")  # 경영관리 → 조건부 라우팅

    workflow.add_conditional_edges(
        "INCREMENT_ROUND",
        lambda s: (
            AgentType.FI if s["current_round"] > s["max_rounds"] else AgentType.TR
        ),
        [AgentType.FI, AgentType.TR],
    )

    workflow.set_entry_point(AgentType.TR)
    workflow.add_edge(AgentType.FI, END)

    # 그래프 컴파일
    return workflow.compile()


if __name__ == "__main__":

    graph = create_review_graph(True)

    graph_image = graph.get_graph().draw_mermaid_png()

    output_path = "review_graph.png"
    with open(output_path, "wb") as f:
        f.write(graph_image)

    import subprocess

    subprocess.run(["open", output_path])
