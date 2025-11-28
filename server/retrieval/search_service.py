import streamlit as st
from typing import List, Literal
from duckduckgo_search import DDGS
from server.utils.config import get_llm

try:
    # ✅ 최신 LangChain 구조 (0.1.x 이상)
    from langchain_core.documents import Document
except ImportError:
    # ✅ 구버전 호환
    from langchain.schema import Document

try:
    # ✅ 최신 LangChain 구조 (0.1.x 이상)
    from langchain_core.messages import HumanMessage, SystemMessage
except ImportError:
    # ✅ 구버전 호환
    from langchain.schema import HumanMessage, SystemMessage



def improve_search_query(
    agenda: str,
    role: Literal["TR_AGENT", "CO_AGENT", "FI_AGENT"] = "FI_AGENT",
) -> List[str]:

    template = "'{agenda}'에 대해 {perspective} 웹검색에 적합한 3개의 검색어를 제안해주세요. 각 검색어는 25자 이내로 작성하고 콤마로 구분하세요. 검색어만 제공하고 설명은 하지 마세요."

    perspective_map = {
        "TR_AGENT": "자금 컨설턴트 입장을 뒷받침할 수 있는 사실과 정보를 찾고자 합니다.",
        "CO_AGENT": "경영관리 컨설턴트 입장을 뒷받침할 수 있는 사실과 정보를 찾고자 합니다.",
        "FI_AGENT": "재무회계 컨설턴트 입장의 객관적인 사실과 정보를 찾고자 합니다.",
    }

    prompt = template.format(agenda=agenda, perspective=perspective_map[role])

    messages = [
        SystemMessage(
            content="당신은 검색 전문가입니다. 주어진 주제에 대해 가장 관련성 높은 검색어를 제안해주세요."
        ),
        HumanMessage(content=prompt),
    ]

    # 스트리밍 응답 받기
    response = get_llm().invoke(messages)

    # ,로 구분된 검색어 추출
    suggested_queries = [q.strip() for q in response.content.split(",")]

    return suggested_queries[:3]


def get_search_content(
    improved_queries: str,
    language: str = "ko",
    max_results: int = 5,
) -> List[Document]:

    try:
        documents = []

        ddgs = DDGS()

        # 각 개선된 검색어에 대해 검색 수행
        for query in improved_queries:
            try:
                # 검색 수행
                results = ddgs.text(
                    query,
                    region=language,
                    safesearch="moderate",
                    timelimit="y",  # 최근 1년 내 결과
                    max_results=max_results,
                )

                if not results:
                    continue

                # 검색 결과 처리
                for result in results:
                    title = result.get("title", "")
                    body = result.get("body", "")
                    url = result.get("href", "")

                    if body:
                        documents.append(
                            Document(
                                page_content=body,
                                metadata={
                                    "source": url,
                                    "section": "content",
                                    "agenda": title,
                                    "query": query,
                                },
                            )
                        )

            except Exception as e:
                st.warning(f"검색 중 오류 발생: {str(e)}")

        return documents

    except Exception as e:
        st.error(f"검색 서비스 오류 발생: {str(e)}")
        return []
