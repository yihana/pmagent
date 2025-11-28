# server/routers/workflow.py
from __future__ import annotations
import json
import os
import time
import uuid
import logging
import asyncio
from typing import Any, Dict, Iterator, Optional, List
from fastapi import APIRouter, HTTPException, Request, Query
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
from server.workflow.state import AgentType, ReviewState
from server.workflow.graph import create_review_graph

# Langfuse 콜백(옵션)
try:
    from langfuse.callback import CallbackHandler  # type: ignore
    ENABLE_LANGFUSE = True
except Exception:
    CallbackHandler = None  # type: ignore
    ENABLE_LANGFUSE = False

router = APIRouter(
    prefix="/api/v1/workflow",
    tags=["workflow"],
    responses={404: {"description": "Not found"}},
)

log = logging.getLogger("uvicorn.error")


# ---------- 입력/출력 모델 ----------
class WorkflowRequest(BaseModel):
    agenda: str
    max_rounds: int = 3
    enable_rag: bool = True


# ---------- SSE 유틸 ----------
def _sse(event: Dict[str, Any]) -> bytes:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n".encode("utf-8")


# ---------- 그래프 청크 파서 ----------
def _extract_update_state_from_chunk(chunk: Any) -> Optional[Dict[str, Any]]:
    """
    원본 프론트가 기대하는 형태:
      event: { type: "update", data: { role, response, agenda, messages, current_round, max_rounds, docs } }
    LangGraph stream에서 (node, subgraph) 구조일 때 subgraph["update_state"]에 위 필드들이 들어오는 구현을 지원.
    """
    try:
        if isinstance(chunk, (tuple, list)) and len(chunk) >= 2:
            node, subgraph = chunk[0], chunk[1]
            if isinstance(subgraph, dict):
                upd = subgraph.get("update_state")
                if isinstance(upd, dict):
                    response = upd.get("response")
                    review_state = upd.get("review_state") or {}
                    messages = review_state.get("messages", [])
                    current_round = review_state.get("current_round")
                    max_rounds = review_state.get("max_rounds")
                    docs = review_state.get("docs", {})
                    agenda = review_state.get("agenda")

                    role = None
                    try:
                        node_name = node[0] if isinstance(node, (tuple, list)) and node else node
                        if isinstance(node_name, str):
                            role = node_name.split(":")[0]
                    except Exception:
                        pass

                    return {
                        "role": role or "SYSTEM",
                        "response": response,
                        "agenda": agenda,
                        "messages": messages,
                        "current_round": current_round,
                        "max_rounds": max_rounds,
                        "docs": docs,
                    }
    except Exception:
        pass
    return None


def _extract_text_from_chunk(chunk: Any) -> str:
    """update_state가 없고 텍스트만 있는 경우 대비(보조 경로)."""
    try:
        if isinstance(chunk, dict):
            for k in ("text", "content", "delta"):
                v = chunk.get(k)
                if isinstance(v, str) and v:
                    return v
            upd = chunk.get("updates")
            if isinstance(upd, dict):
                for v in upd.values():
                    if isinstance(v, dict):
                        c = v.get("content") or v.get("text")
                        if isinstance(c, str) and c:
                            return c
        if hasattr(chunk, "choices"):
            c0 = getattr(chunk.choices[0], "delta", None)
            if c0 is not None and hasattr(c0, "content"):
                return getattr(c0, "content") or ""
    except Exception:
        pass
    return ""


# ---------- 디버그용 핑 스트림 ----------
@router.get("/debug/sse-ping")
def sse_ping(count: int = Query(20, ge=1, le=500), interval_ms: int = Query(250, ge=10, le=5000)):
    rid = str(uuid.uuid4())

    def gen() -> Iterator[bytes]:
        log.info("[SSE-PING %s] start count=%s interval=%sms", rid, count, interval_ms)
        try:
            yield _sse({"type": "start", "rid": rid})
            for i in range(1, count + 1):
                yield _sse({"type": "tick", "rid": rid, "i": i})
                time.sleep(interval_ms / 1000.0)
            yield _sse({"type": "end", "rid": rid})
            log.info("[SSE-PING %s] end ok", rid)
        except Exception as e:
            log.exception("[SSE-PING %s] error: %s", rid, e)
            yield _sse({"type": "error", "rid": rid, "message": str(e)})

    headers = {"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"}
    return StreamingResponse(gen(), media_type="text/event-stream", headers=headers)


# ---------- 논스트림 (문제 분리용) ----------
@router.post("/review/run")
async def review_run(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except Exception:
        body = {}
    agenda = body.get("agenda") or ""
    max_rounds = int(body.get("max_rounds") or body.get("rounds") or 1)
    enable_rag = bool(body.get("enable_rag") or body.get("rag_enabled") or False)

    # graph.py 기준으로 그래프 생성 (세션ID는 임의)
    session_id = str(uuid.uuid4())
    graph = create_review_graph(enable_rag=enable_rag, session_id=session_id)  # :contentReference[oaicite:3]{index=3}

    # reviewState 초기 상태(원본 스키마)
    initial_state = {
        "agenda": agenda,
        "messages": [],
        "current_round": 1,
        "max_rounds": max_rounds,
        "prev_node": "START",
        "docs": {},
    }

    callbacks = []
    if ENABLE_LANGFUSE and CallbackHandler:
        try:
            callbacks = [CallbackHandler(session_id=session_id)]
        except Exception as e:
            log.warning("Langfuse 콜백 생성 실패: %s", e)

    try:
        parts: List[str] = []
        for ch in graph.stream(
            initial_state,
            stream_mode="updates",
            config={"callbacks": callbacks} if callbacks else None,
        ):
            st = _extract_update_state_from_chunk(ch)
            if st and isinstance(st.get("response"), str):
                parts.append(st["response"])
                continue
            t = _extract_text_from_chunk(ch)
            if t:
                parts.append(t)
        return JSONResponse({"text": "".join(parts)})
    except Exception as e:
        log.exception("[RUN] error: %s", e)
        raise HTTPException(500, f"review_run failed: {e}")


# ---------- 스트리밍(SSE) ----------
@router.post("/review/stream")
async def stream_review_workflow(request: WorkflowRequest):
    agenda = request.agenda
    max_rounds = request.max_rounds
    enable_rag = request.enable_rag

    session_id = str(uuid.uuid4())
    try:
        review_graph = create_review_graph(enable_rag, session_id)

    except Exception as e:
        raise HTTPException(500, f"review_graph 생성 실패: {e}")

    # reviewState 초기 상태(원본 스키마)
    initial_state: ReviewState = {
        "agenda": agenda,
        "messages": [],
        "current_round": 1,
        "max_rounds": max_rounds,
        "prev_node": "START",  # 이전 노드 START로 설정
        "docs": {},  # RAG 결과 저장
    }

    langfuse_handler = CallbackHandler(session_id=session_id)

    callbacks = []
    if ENABLE_LANGFUSE and CallbackHandler:
        try:
            callbacks = [CallbackHandler(session_id=session_id)]
        except Exception as e:
            log.warning("Langfuse 콜백 생성 실패: %s", e)

        # 스트리밍 응답 반환
    return StreamingResponse(
        review_generator(review_graph, initial_state, langfuse_handler),
        media_type="text/event-stream",
    )


async def review_generator(review_graph, initial_state, langfuse_handler):
    for chunk in review_graph.stream(
        initial_state,
        config={"callbacks": [langfuse_handler]},
        subgraphs=True,
        stream_mode="updates",
    ):
        state = _extract_update_state_from_chunk(chunk)
        if state:
            yield _sse({"type": "update", "data": state})
        else:
            text = _extract_text_from_chunk(chunk)
            if text:
                yield _sse({"type": "delta", "text": text})

        await asyncio.sleep(0.01)

    yield _sse({"type": "end", "data": {}})




