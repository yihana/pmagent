# server/workflow/state.py
# LangGraph 상태 정의 - RAG 관련 필드 추가
from typing import Dict, List, TypedDict, Optional, Any

class AgentType:
    TR = "TR_AGENT"
    CO = "CO_AGENT"
    FI = "FI_AGENT"

    @classmethod
    def to_korean(cls, role: str) -> str:
        if role == cls.TR:
            return "자금"
        elif role == cls.CO:
            return "경영관리"
        elif role == cls.FI:
            return "재무회계"
        else:
            return role


class ReviewState(TypedDict):
    agenda: str
    messages: List[Dict]
    current_round: int
    prev_node: str
    max_rounds: int
    docs: Dict[str, List]  # RAG 검색 결과
    contexts: Dict[str, str]  # RAG 검색 컨텍스트
    

class PMState(TypedDict, total=False):
    # 입력
    project_id: int
    doc_type: str                 # "meeting" | "rfp" | "proposal" | "issue"
    title: str
    text: str                     # 문서/회의록 본문
    week_start: str               # "YYYY-MM-DD"
    week_end: str                 # "YYYY-MM-DD"
    db: Any                       # SQLAlchemy Session (FastAPI DI에서 주입)

    # 중간/출력
    document_id: int
    action_items: List[Dict[str, Any]]
    risks: List[Dict[str, Any]]
    report_md: str
    snapshot: Dict[str, Any]
