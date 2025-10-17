#server > main
from dotenv import load_dotenv
load_dotenv()
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from server.workflow.state import AgentType, DebateState
import uvicorn
from fastapi import FastAPI

# 절대 경로 임포트로 수정
from server.routers import workflow

# ✅ 모델/DB 임포트 순서 정리
from server.db.database import Base, engine
# 🔑 모델을 먼저 등록 (사이드이펙트 없이 레지스트리에만 올림)
from server.db import pm_models  # noqa: F401

# 🔑 매퍼를 강제로 구성
from sqlalchemy.orm import configure_mappers
configure_mappers()

from server.routers import pm_work
from server.routers import history

# 데이터베이스 초기화 (모델 등록/매퍼 구성 뒤에 실행)
Base.metadata.create_all(bind=engine)

# FastAPI 인스턴스 생성
app = FastAPI(
    title="PM Agent v0.9",
    description="AI PM Copilot 서비스를 위한 API",
    version="0.4.1",
)

print(">>> AOAI_DEPLOY_GPT5O =", os.getenv("AOAI_DEPLOY_GPT4O"))

# router 추가
app.include_router(history.router)
app.include_router(workflow.router)
app.include_router(pm_work.router)

# 실행은 server 경로에서
# . venv/bin/activate
# uvicorn main:app --port=8001
