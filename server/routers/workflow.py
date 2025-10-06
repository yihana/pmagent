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

# ✅ debate는 원래 graph.py 사용
from server.workflow.graph import create_debate_graph  # :contentReference[oaicite:2]{index=2}

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
    topic: str
    max_rounds: int = 3
    enable_rag: bool = True


# ---------- SSE 유틸 ----------
def _sse(event: Dict[str, Any]) -> bytes:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n".encode("utf-8")


# ---------- 그래프 청크 파서 ----------
def _extract_update_state_from_chunk(chunk: Any) -> Optional[Dict[str, Any]]:
    """
    원본 프론트가 기대하는 형태:
      event: { type: "update", data: { role, response, topic, messages, current_round, max_rounds, docs } }
    LangGraph stream에서 (node, subgraph) 구조일 때 subgraph["update_state"]에 위 필드들이 들어오는 구현을 지원.
    """
    try:
        if isinstance(chunk, (tuple, list)) and len(chunk) >= 2:
            node, subgraph = chunk[0], chunk[1]
            if isinstance(subgraph, dict):
                upd = subgraph.get("update_state")
                if isinstance(upd, dict):
                    response = upd.get("response")
                    debate_state = upd.get("debate_state") or {}
                    messages = debate_state.get("messages", [])
                    current_round = debate_state.get("current_round")
                    max_rounds = debate_state.get("max_rounds")
                    docs = debate_state.get("docs", {})
                    topic = debate_state.get("topic")

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
                        "topic": topic,
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
@router.post("/debate/run")
async def debate_run(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except Exception:
        body = {}
    topic = body.get("topic") or ""
    max_rounds = int(body.get("max_rounds") or body.get("rounds") or 1)
    enable_rag = bool(body.get("enable_rag") or body.get("rag_enabled") or False)

    # graph.py 기준으로 그래프 생성 (세션ID는 임의)
    session_id = str(uuid.uuid4())
    graph = create_debate_graph(enable_rag=enable_rag, session_id=session_id)  # :contentReference[oaicite:3]{index=3}

    # DebateState 초기 상태(원본 스키마)
    initial_state = {
        "topic": topic,
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
        raise HTTPException(500, f"debate_run failed: {e}")


# ---------- 스트리밍(SSE) ----------
@router.post("/debate/stream")
async def stream_debate_workflow(request: WorkflowRequest, debug: int = Query(0)) -> StreamingResponse:
    topic = request.topic
    max_rounds = request.max_rounds
    enable_rag = request.enable_rag

    # graph.py 기준으로 그래프 생성 (세션ID는 임의)
    session_id = str(uuid.uuid4())
    try:
        graph = create_debate_graph(enable_rag=enable_rag, session_id=session_id)  # :contentReference[oaicite:4]{index=4}
    except Exception as e:
        raise HTTPException(500, f"debate_graph 생성 실패: {e}")

    # DebateState 초기 상태(원본 스키마)
    initial_state = {
        "topic": topic,
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

    async def debate_generator():
        rid = str(uuid.uuid4())
        beat_at = time.time()
        sent = 0
        try:
            log.info("[STREAM %s] start topic=%r rounds=%s rag=%s", rid, topic, max_rounds, enable_rag)
            if debug:
                yield _sse({"type": "start", "rid": rid, "state": initial_state})

            for ch in graph.stream(
                initial_state,
                config={"callbacks": callbacks} if callbacks else None,
                subgraphs=True,
                stream_mode="updates",
            ):
                sent += 1

                # 1) 원래 포맷: update_state가 있으면 'update' 이벤트로 전송
                state = _extract_update_state_from_chunk(ch)
                if state:
                    yield _sse({"type": "update", "data": state})
                else:
                    # 2) 텍스트만 오면 delta로 보조 전송
                    text = _extract_text_from_chunk(ch)
                    if text:
                        yield _sse({"type": "delta", "text": text})

                if debug:
                    # 원시 chunk 일부도 내려서 추적 가능
                    try:
                        raw = ch if isinstance(ch, dict) else str(ch)
                        raw_s = json.dumps(raw, ensure_ascii=False) if isinstance(raw, dict) else raw
                        raw_s = (raw_s[:400] + "...") if len(raw_s) > 400 else raw_s
                    except Exception:
                        raw_s = None
                    yield _sse({"type": "log", "rid": rid, "note": f"chunk#{sent}", "raw": raw_s})

                # 하트비트(10초)
                now = time.time()
                if now - beat_at > 10:
                    yield _sse({"type": "beat", "rid": rid, "sent": sent})
                    beat_at = now

                await asyncio.sleep(0.01)

            yield _sse({"type": "end", "data": {}})
            log.info("[STREAM %s] end ok (chunks=%s)", rid, sent)

        except BrokenPipeError:
            log.warning("[STREAM %s] client disconnected (BrokenPipe)", rid)
        except Exception as e:
            log.exception("[STREAM %s] error: %s", rid, e)
            yield _sse({"type": "error", "rid": rid, "message": str(e)})

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    return StreamingResponse(debate_generator(), media_type="text/event-stream", headers=headers)
