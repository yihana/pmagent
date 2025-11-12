from __future__ import annotations
import os, re, json, asyncio, time, logging, traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import FAISS

from server.workflow.agents.scope_agent.prompts import build_scope_prompt

logger = logging.getLogger("scope.agent")

# ---------------------------------------------------------------------
# LLM getter
# ---------------------------------------------------------------------
def get_llm():
    try:
        from server.utils.config import get_llm as _g
        llm = _g()
        logger.debug(f"[SCOPE] LLM 로드 성공: {type(llm).__name__}")
        return llm
    except Exception as e:
        logger.warning(f"[SCOPE] get_llm 실패: {e}")
        return None

# ---------------------------------------------------------------------
# 응답 텍스트 추출
# ---------------------------------------------------------------------
def _safe_extract_raw(resp):
    try:
        if resp is None: return ""
        if isinstance(resp, str): return resp
        if hasattr(resp, "content"): return str(resp.content)
        if hasattr(resp, "choices"):
            c = resp.choices
            if isinstance(c, list) and len(c):
                first = c[0]
                if hasattr(first, "message"):
                    m = getattr(first.message, "content", "")
                    return m
                if hasattr(first, "text"):
                    return first.text
        return str(resp)
    except Exception as e:
        logger.warning(f"[SCOPE] raw extract 실패: {e}")
        return str(resp)

# ---------------------------------------------------------------------
# JSON 파서
# ---------------------------------------------------------------------
def _json_from_text(text: str) -> Optional[dict]:
    if not text: return None
    try:
        t = re.sub(r"```json|```", "", text.strip())
        m = re.search(r"(\{[\s\S]*\})", t)
        if m:
            return json.loads(m.group(1))
        if t.startswith("{") and t.endswith("}"):
            return json.loads(t)
    except Exception as e:
        logger.error(f"[SCOPE] JSON 파싱 실패: {e}")
    return None

# ---------------------------------------------------------------------
# Confidence 추정
# ---------------------------------------------------------------------
def _estimate_confidence(resp_json: Optional[dict], raw_text: str) -> float:
    if not resp_json or not isinstance(resp_json, dict): return 0.1
    reqs = resp_json.get("requirements", [])
    if not reqs: return 0.1
    count = len(reqs)
    base = 0.6 if count >= 5 else 0.4
    filled = sum(1 for r in reqs if all(r.get(k) for k in ["req_id","title","description"]))
    ac = sum(1 for r in reqs if isinstance(r.get("acceptance_criteria"), list))
    score = base + 0.2*(filled/len(reqs)) + 0.1*(ac/len(reqs))
    return min(score, 0.99)

# ---------------------------------------------------------------------
# PromptManager: RAG + 압축 + 캐싱
# ---------------------------------------------------------------------
class PromptManager:
    def __init__(self):
        self.llm = get_llm()
        self.vectorstore = None
        self._init_vectorstore()

    def _init_vectorstore(self):
        texts, metas = [], []
        for p in Path("templates").rglob("*.txt"):
            t = p.read_text(encoding="utf-8", errors="ignore")
            texts.append(t); metas.append({"name": str(p.relative_to("templates"))})
        for p in Path("rules").rglob("*.txt"):
            t = p.read_text(encoding="utf-8", errors="ignore")
            texts.append(t); metas.append({"name": str(p.relative_to("rules"))})
        if not texts: return
        try:
            self.vectorstore = FAISS.from_texts(texts, metadatas=metas, embedding=OpenAIEmbeddings())
            logger.info(f"[PROMPT-RAG] 벡터스토어 초기화 완료 ({len(texts)} docs)")
        except Exception as e:
            logger.warning(f"[PROMPT-RAG] 초기화 실패: {e}")

    def build_rag_prompt(self, text: str, base_prompt=None, k=3) -> str:
        if not self.vectorstore:
            return base_prompt or build_scope_prompt(text)
        results = self.vectorstore.similarity_search(text, k=k)
        retrieved = "\n\n".join(r.page_content for r in results)
        base = base_prompt or "당신은 PMP 표준을 준수하는 PM 분석가입니다."
        return f"{base}\n\n{retrieved}\n\n문서:\n{text[:8000]}"

    def compress_prompt(self, prompt: str) -> str:
        if not self.llm or len(prompt) < 10000:
            return prompt
        try:
            msg = [{"role": "user", "content": f"아래 프롬프트를 50% 길이로 압축:\n{prompt}"}]
            resp = self.llm.invoke(msg)
            return _safe_extract_raw(resp)
        except Exception as e:
            logger.warning(f"[PROMPT-RAG] 압축 실패: {e}")
            return prompt

# ---------------------------------------------------------------------
# ScopeAgent (기존 기능 유지 + 개선 통합)
# ---------------------------------------------------------------------
class ScopeAgent:
    def __init__(self, data_dir: Optional[str] = None):
        self.llm = get_llm()
        self.pmgr = PromptManager()
        self.data_dir = data_dir or "data"
        logger.info(f"[SCOPE_AGENT] 초기화 완료 (data_dir={self.data_dir})")

    async def _call_llm(self, prompt: str):
        if not self.llm:
            raise RuntimeError("LLM이 설정되지 않았습니다.")
        if hasattr(self.llm, "invoke"):
            msgs = [
                {"role": "system", "content": "You are a PM analyst."},
                {"role": "user", "content": prompt, "cache_control": {"type": "ephemeral"}}
            ]
            return await asyncio.to_thread(self.llm.invoke, msgs)
        else:
            return await asyncio.to_thread(self.llm, prompt)

    async def _extract_items_with_confidence(self, text: str, threshold=0.75, max_attempts=3):
        attempt, last_json, last_raw = 0, None, ""
        while attempt < max_attempts:
            attempt += 1
            logger.info(f"[SCOPE] 시도 {attempt}/{max_attempts}")
            prompt = self.pmgr.build_rag_prompt(text) if not last_json else \
                f"이전 결과 개선:\n{json.dumps(last_json, ensure_ascii=False)[:1500]}\n\n{text[:6000]}"
            prompt = self.pmgr.compress_prompt(prompt)
            try:
                resp = await self._call_llm(prompt)
                raw = _safe_extract_raw(resp)
                parsed = _json_from_text(raw)
                conf = _estimate_confidence(parsed, raw)
                if parsed and conf >= threshold:
                    logger.info(f"✅ 성공: conf={conf:.2f}")
                    return parsed, raw
                last_json, last_raw = parsed, raw
                await asyncio.sleep(0.3)
            except Exception as e:
                logger.error(f"[SCOPE] LLM 호출 실패: {e}")
                await asyncio.sleep(0.5)
        logger.warning("[SCOPE] 최대 시도 도달. 마지막 결과 반환.")
        return last_json or {"requirements": []}, last_raw

    async def pipeline(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        text = payload.get("text") or ""
        options = payload.get("options", {})
        confidence_threshold = float(options.get("confidence_threshold", 0.75))
        max_attempts = int(options.get("max_attempts", 3))
        project_id = payload.get("project_id", "Unknown")

        items, raw_resp = await self._extract_items_with_confidence(
            text, confidence_threshold, max_attempts
        )

        out_dir = Path("data/outputs/scope") / str(project_id)
        out_dir.mkdir(parents=True, exist_ok=True)

        srs_path = out_dir / f"{project_id}_SRS.md"
        self._generate_srs(project_id, items, srs_path)
        wbs = await self._synthesize_wbs_draft(items)
        wbs_path = out_dir / "wbs_structure.json"
        wbs_path.write_text(json.dumps(wbs, ensure_ascii=False, indent=2), encoding="utf-8")

        return {
            "status": "ok",
            "project_id": project_id,
            "requirements": items.get("requirements", []),
            "wbs": wbs,
            "srs_path": str(srs_path),
            "_llm_raw": raw_resp[:2000],
        }

    def _generate_srs(self, project_id, items, path: Path):
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"# Software Requirements Specification\n\n")
            for r in items.get("requirements", []):
                f.write(f"### {r.get('req_id','')}: {r.get('title','')}\n")
                f.write(f"- Type: {r.get('type')}\n")
                f.write(f"- Priority: {r.get('priority')}\n")
                f.write(f"- Description: {r.get('description')}\n\n")

    async def _synthesize_wbs_draft(self, items, depth=3):
        reqs = items.get("requirements", [])
        nodes = [{"id": "WBS-1", "name": "Project", "level": 1, "children": []}]
        per = max(1, (len(reqs) + 2) // 3)
        for i in range(3):
            phase = {"id": f"WBS-1.{i+1}", "name": f"Phase {i+1}", "level": 2, "children": []}
            for j, r in enumerate(reqs[i*per:(i+1)*per], 1):
                phase["children"].append({
                    "id": f"{phase['id']}.{j}",
                    "name": r.get("title", f"Task {i+1}.{j}")[:60],
                    "level": 3
                })
            nodes[0]["children"].append(phase)
        return {"nodes": nodes, "depth": depth}

# ---------------------------------------------------------------------
# 체인 파이프라인 (Scope → Quality → Schedule)
# ---------------------------------------------------------------------
class ScopeChainPipeline:
    def __init__(self, scope_agent, quality_agent, schedule_agent):
        self.scope_agent = scope_agent
        self.quality_agent = quality_agent
        self.schedule_agent = schedule_agent

    async def run(self, text, project_meta=None):
        logger.info("🚀 Scope → Quality → Schedule 체인 시작")
        scope_res = await self.scope_agent._extract_items_with_confidence(text)
        reqs = scope_res[0].get("requirements", [])
        valid = self.quality_agent.validate(reqs, text, project_meta)
        if not valid.get("pass", True):
            logger.info("🔄 품질 미달 → 재추출 시도")
            reqs = self.scope_agent.refine_requirements(text, reqs, valid, project_meta)
        wbs = await self.schedule_agent.generate_wbs(reqs)
        return {"requirements": reqs, "validation": valid, "wbs": wbs, "status": "complete"}
