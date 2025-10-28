# app/pages/pm_scope.py
# Scope Agent 전용 페이지 (수정됨)
import streamlit as st
import requests
import json
from pathlib import Path

API_BASE = st.secrets.get("API_BASE", "http://127.0.0.1:8001/api/v1/pm")

st.title("🔎 Scope Agent — RFP 분석")

# ✅ 세션 상태 초기화
if "uploaded_path" not in st.session_state:
    st.session_state["uploaded_path"] = ""
if "sample_rfp" not in st.session_state:
    st.session_state["sample_rfp"] = ""

# ============================================
# 1. 입력 폼
# ============================================
with st.form("scope_form"):
    st.markdown("### 프로젝트 정보")
    col1, col2 = st.columns(2)
    with col1:
        project_name = st.text_input("프로젝트명", value="Demo Project")
    with col2:
        methodology = st.selectbox("방법론", ["waterfall", "agile"], index=0)
    
    st.markdown("### RFP 입력 방법")
    input_method = st.radio(
        "선택",
        ["직접 입력", "서버 파일 경로"],
        horizontal=True
    )
    
    if input_method == "직접 입력":
        # ✅ 세션에 샘플이 있으면 자동으로 채워짐
        default_text = st.session_state.get("sample_rfp", "")
        rfp_text = st.text_area(
            "RFP 내용",
            value=default_text,
            height=300,
            placeholder="""# 프로젝트 RFP

## 1. 프로젝트 개요
...

## 2. 요구사항
- 사용자 인증 기능
- 데이터 암호화
...
"""
        )
        rfp_path = None
    else:
        rfp_text = None
        # ✅ 업로드된 경로가 있으면 자동으로 채워짐
        default_path = st.session_state.get("uploaded_path", "data/inputs/RFP/sample_rfp.txt")
        rfp_path = st.text_input(
            "서버 파일 경로",
            value=default_path,
            help="서버에 업로드된 RFP 파일 경로 (.txt, .md, .pdf)"
        )
    
    with st.expander("⚙️ 옵션"):
        chunk_size = st.number_input("Chunk Size", 100, 2000, 500, 50)
        overlap = st.number_input("Overlap", 0, 500, 100, 10)
    
    submitted = st.form_submit_button("🔎 Scope 추출 실행", type="primary")

# ============================================
# 2. Scope 실행
# ============================================
if submitted:
    # ✅ 입력 검증
    if input_method == "직접 입력":
        if not rfp_text or not rfp_text.strip():
            st.error("❌ RFP 내용을 입력하세요.")
            st.stop()
        
        # ✅ 텍스트 직접 전달
        payload = {
            "project_id": project_name,
            "text": rfp_text,
            "methodology": methodology,
            "options": {"chunk_size": chunk_size, "overlap": overlap}
        }
    else:
        if not rfp_path or not rfp_path.strip():
            st.error("❌ RFP 파일 경로를 입력하세요.")
            st.stop()
        
        # ✅ 파일 경로 전달 (서버에서 읽음)
        payload = {
            "project_id": project_name,
            "documents": [{"path": rfp_path, "type": "RFP"}],
            "methodology": methodology,
            "options": {"chunk_size": chunk_size, "overlap": overlap}
        }
    
    st.info("📤 요청 전송 중...")
    
    try:
        with st.spinner("Scope Agent 실행 중... (최대 3분 소요)"):
            resp = requests.post(
                f"{API_BASE}/scope/analyze", 
                json=payload, 
                timeout=180
            )
            data = resp.json()
    except requests.exceptions.Timeout:
        st.error("❌ 요청 시간 초과 (3분). 서버를 확인하세요.")
        st.stop()
    except Exception as e:
        st.error(f"❌ API 호출 실패: {e}")
        st.stop()
    
    # ============================================
    # 3. 결과 표시
    # ============================================
    if resp.status_code == 200:
        st.success("✅ Scope 추출 완료")
        
        # ✅ 요구사항 표시
        st.markdown("### 📋 추출된 요구사항")
        requirements = data.get("requirements", [])
        
        if requirements:
            st.metric("총 요구사항 수", len(requirements))
            
            # 우선순위별 필터
            priority_filter = st.multiselect(
                "우선순위 필터",
                ["High", "Medium", "Low"],
                default=["High", "Medium", "Low"]
            )
            
            filtered = [r for r in requirements if r.get("priority") in priority_filter]
            
            # 테이블로 표시
            for req in filtered:
                with st.expander(f"**{req.get('req_id')}**: {req.get('title')} `[{req.get('priority')}]`"):
                    st.markdown(f"**유형**: {req.get('type')}")
                    st.markdown(f"**설명**: {req.get('description')}")
                    st.markdown(f"**출처**: {req.get('source_span')}")
        else:
            st.warning("⚠️ 추출된 요구사항이 없습니다.")
        
        # ✅ 기능 표시
        functions = data.get("functions", [])
        if functions:
            with st.expander(f"🔧 기능 목록 ({len(functions)}개)"):
                for func in functions:
                    st.markdown(f"- **{func.get('id')}**: {func.get('title')}")
        
        # ✅ 산출물 표시
        deliverables = data.get("deliverables", [])
        if deliverables:
            with st.expander(f"📦 산출물 목록 ({len(deliverables)}개)"):
                for deliv in deliverables:
                    st.markdown(f"- **{deliv.get('id')}**: {deliv.get('title')}")
        
        # ✅ 승인기준 표시
        acceptance = data.get("acceptance_criteria", [])
        if acceptance:
            with st.expander(f"✅ 승인기준 ({len(acceptance)}개)"):
                for acc in acceptance:
                    st.markdown(f"- **{acc.get('id')}**: {acc.get('title')}")
        
        # ============================================
        # 4. 생성된 파일
        # ============================================
        st.markdown("---")
        st.markdown("### 📁 생성된 산출물")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            req_json = data.get("requirements_json")
            if req_json:
                st.markdown("**Requirements JSON**")
                st.code(req_json, language="text")
        
        with col2:
            srs = data.get("srs_path")
            if srs:
                st.markdown("**SRS (Markdown)**")
                st.code(srs, language="text")
        
        with col3:
            rtm_csv = data.get("rtm_csv")
            if rtm_csv:
                st.markdown("**RTM (CSV)**")
                st.code(rtm_csv, language="text")
        
        # ✅ PMP 산출물
        pmp_outputs = data.get("pmp_outputs", {})
        if pmp_outputs:
            with st.expander("📊 PMP 표준 산출물"):
                for name, path in pmp_outputs.items():
                    if path:
                        st.text(f"✅ {name}: {path}")
        
        # ✅ 세션 저장 (Schedule Agent에서 사용)
        st.session_state["requirements"] = requirements
        st.session_state["project_name"] = project_name
        st.session_state["methodology"] = methodology
        st.session_state["scope_completed"] = True
        
        # ============================================
        # 5. 다음 단계 안내
        # ============================================
        st.markdown("---")
        st.success("💡 **다음 단계**: Schedule 페이지로 이동하여 WBS 및 일정을 생성하세요.")
        
        if st.button("➡️ Schedule 페이지로 이동"):
            st.switch_page("pages/pm_schedule.py")
        
        # 전체 응답
        with st.expander("🔍 전체 응답 (JSON)"):
            st.json(data)
    
    elif resp.status_code == 400:
        st.error(f"❌ 요청 오류 (400): {data.get('detail', 'Unknown error')}")
        st.code(json.dumps(data, indent=2))
    
    else:
        st.error(f"❌ 서버 오류 ({resp.status_code})")
        st.code(resp.text)

# ============================================
# 6. 파일 업로드 (사이드바)
# ============================================
with st.sidebar:
    st.markdown("### 📤 파일 업로드")
    
    upload = st.file_uploader(
        "RFP 파일",
        type=["pdf", "txt", "md"],
        help="PDF, TXT, MD 파일 지원"
    )
    
    if upload and st.button("업로드", type="primary"):
        try:
            # 파일 타입에 따른 MIME type 설정
            mime_types = {
                ".pdf": "application/pdf",
                ".txt": "text/plain",
                ".md": "text/markdown"
            }
            ext = Path(upload.name).suffix.lower()
            mime = mime_types.get(ext, "application/octet-stream")
            
            files = {"file": (upload.name, upload.getvalue(), mime)}
            
            with st.spinner("업로드 중..."):
                res = requests.post(
                    f"{API_BASE}/upload/rfp", 
                    files=files, 
                    timeout=60
                )
            
            if res.status_code == 200:
                result = res.json()
                path = result.get("path")
                st.success(f"✅ 업로드 완료")
                st.code(path)
                st.info("📋 위 경로를 복사하여 '서버 파일 경로'에 입력하세요.")
            else:
                st.error(f"❌ 업로드 실패 ({res.status_code})")
                st.code(res.text)
        except Exception as e:
            st.error(f"❌ 오류: {e}")
    
    st.markdown("---")
    
    # ✅ 샘플 RFP 버튼
    if st.button("📄 샘플 RFP 사용"):
        st.session_state["sample_rfp"] = """# 전자상거래 플랫폼 구축 RFP

## 1. 프로젝트 개요
온라인 쇼핑몰 시스템 구축

## 2. 기능 요구사항

### 2.1 사용자 관리
- 회원가입 및 로그인 기능
- 소셜 로그인 지원 (Google, Naver, Kakao)
- 프로필 관리

### 2.2 상품 관리
- 상품 검색 및 필터링
- 상품 상세 정보 표시
- 리뷰 및 평점 시스템

### 2.3 주문 및 결제
- 장바구니 기능
- 다양한 결제 수단 지원
- 주문 내역 조회

### 2.4 관리자 기능
- 대시보드
- 상품 관리
- 주문 관리
- 회원 관리

## 3. 비기능 요구사항

### 3.1 성능
- 페이지 로딩 시간: 2초 이내
- 동시 접속자: 1,000명 지원
- 응답 시간: 평균 1초 이내

### 3.2 보안
- HTTPS 통신 필수
- 개인정보 암호화
- SQL Injection 방어
- XSS 방어

### 3.3 가용성
- 시스템 가동률: 99.9% 이상
- 데이터 백업: 일 1회

## 4. 제약사항
- 예산: 1억원
- 기간: 6개월
- 기술스택: React + Python/FastAPI
- 클라우드: AWS
"""
        st.success("✅ 샘플 RFP가 세션에 저장되었습니다. 폼을 다시 제출하세요.")
    
    st.markdown("---")
    st.caption(f"API: {API_BASE}")

# ✅ 샘플 RFP 자동 입력
if "sample_rfp" in st.session_state and input_method == "직접 입력":
    st.info("💡 샘플 RFP가 준비되었습니다. 폼에서 '직접 입력'을 선택하고 제출하세요.")