import os
import streamlit as st
import requests
import json
from utils.state_manager import reset_session_state

# 포트 충돌 방지를 위해 환경변수 사용
# 1) 환경 변수 로드 + 기본값 설정
DEFAULT_API_BASE = "http://localhost:8001/api/v1"

if "API_BASE_URL" not in st.session_state:
    st.session_state["API_BASE_URL"] = os.getenv("API_BASE_URL") or DEFAULT_API_BASE

API_BASE_URL = st.session_state["API_BASE_URL"]


# API로 검토 이력 조회
def fetch_review_history():
    """API를 통해 검토 이력 가져오기"""
    try:
        #review
        API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8001/api/v1")
        response = requests.get(f"{API_BASE_URL}/reviews/")
        
        if response.status_code == 200:
            reviews = response.json()
            # API 응답 형식에 맞게 데이터 변환 (id, agenda, date, rounds)
            return [
                (review["id"], review["agenda"], review["created_at"], review["rounds"])
                for review in reviews
            ]
        else:
            st.error(f"검토 이력 조회 실패: {response.status_code}")
            return []
    except Exception as e:
        st.error(f"API 호출 오류: {str(e)}")
        return []


# API로 특정 검토 데이터 조회
def fetch_review_by_id(review_id):
    """API를 통해 특정 검토 데이터 가져오기"""
    try:
        response = requests.get(f"{API_BASE_URL}/reviews/{review_id}")
        if response.status_code == 200:
            review = response.json()
            agenda = review["agenda"]
            # 실제 API 응답 구조에 맞게 변환 필요
            messages = (
                json.loads(review["messages"])
                if isinstance(review["messages"], str)
                else review["messages"]
            )
            docs = (
                json.loads(review["docs"])
                if isinstance(review["docs"], str)
                else review.get("docs", {})
            )
            return agenda, messages, docs
        else:
            st.error(f"검토 데이터 조회 실패: {response.status_code}")
            return None, None, None
    except Exception as e:
        st.error(f"API 호출 오류: {str(e)}")
        return None, None, None


# API로 검토 삭제
def delete_review_by_id(review_id):
    """API를 통해 특정 검토 삭제"""
    try:
        response = requests.delete(f"{API_BASE_URL}/reviews/{review_id}")
        if response.status_code == 200:
            st.success("검토이 삭제되었습니다.")
            return True
        else:
            st.error(f"검토 삭제 실패: {response.status_code}")
            return False
    except Exception as e:
        st.error(f"API 호출 오류: {str(e)}")
        return False


# API로 모든 검토 삭제
def delete_all_reviews():
    """API를 통해 모든 검토 삭제"""
    try:
        # 모든 검토 목록 조회
        reviews = fetch_review_history()
        if not reviews:
            return True

        # 각 검토 항목 삭제
        success = True
        for review_id, _, _, _ in reviews:
            response = requests.delete(f"{API_BASE_URL}/reviews/{review_id}")
            if response.status_code != 200:
                success = False

        if success:
            st.success("모든 검토이 삭제되었습니다.")
        return success
    except Exception as e:
        st.error(f"API 호출 오류: {str(e)}")
        return False


# API로 검토 저장
def save_review(agenda, rounds, messages, docs=None):
    """API를 통해 검토 결과를 데이터베이스에 저장"""
    try:
        # API 요청 데이터 준비
        review_data = {
            "agenda": agenda,
            "rounds": rounds,
            "messages": (
                json.dumps(messages) if not isinstance(messages, str) else messages
            ),
            "docs": (
                json.dumps(docs)
                if docs and not isinstance(docs, str)
                else (docs or "{}")
            ),
        }

        response = requests.post(f"{API_BASE_URL}/reviews/", json=review_data)

        if response.status_code == 200 or response.status_code == 201:
            st.success("검토이 성공적으로 저장되었습니다.")
            return response.json().get("id")  # 저장된 검토 ID 반환
        else:
            st.error(f"검토 저장 실패: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        st.error(f"API 호출 오류: {str(e)}")
        return None


# 검토 이력 UI 렌더링
def render_history_ui():

    col1, col2 = st.columns([1, 1])

    with col1:
        if st.button("이력 새로고침", use_container_width=True):
            st.rerun()

    with col2:
        if st.button("전체 이력 삭제", type="primary", use_container_width=True):
            if delete_all_reviews():
                st.rerun()

    # 검토 이력 로드
    review_history = fetch_review_history()

    if not review_history:
        st.info("저장된 검토 이력이 없습니다.")
    else:
        render_history_list(review_history)


# 검토 이력 목록 렌더링
def render_history_list(review_history):
    for id, agenda, date, rounds in review_history:
        with st.container(border=True):

            # 검토 주제
            st.write(f"***{agenda}***")

            col1, col2, col3 = st.columns([3, 1, 1])
            # 검토 정보
            with col1:
                st.caption(f"날짜: {date} | 라운드: {rounds}")

            # 보기 버튼
            with col2:
                if st.button("보기", key=f"view_{id}", use_container_width=True):
                    agenda, messages, docs = fetch_review_by_id(id)
                    if agenda and messages:
                        st.session_state.viewing_history = True
                        st.session_state.messages = messages
                        st.session_state.loaded_agenda = agenda
                        st.session_state.loaded_review_id = id
                        st.session_state.docs = docs
                        st.session_state.app_mode = "results"
                        st.rerun()

            # 삭제 버튼
            with col3:
                if st.button("삭제", key=f"del_{id}", use_container_width=True):
                    if delete_review_by_id(id):
                        reset_session_state()
                        st.rerun()
