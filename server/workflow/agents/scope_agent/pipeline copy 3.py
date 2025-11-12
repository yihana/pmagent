from __future__ import annotations
import os, re, json, asyncio, time, logging, traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS

from server.workflow.agents.scope_agent.prompts import build_scope_prompt
from server.workflow.agents.scope_agent.prompts import (
    PROJECT_CHARTER_PROMPT, TAILORING_PROMPT
)

from server.workflow.agents.scope_agent.outputs.project_charter import ProjectCharterGenerator
from server.workflow.agents.scope_agent.outputs.scope_statement import ScopeStatementGenerator
from server.workflow.agents.scope_agent.outputs.rtm_excel import RTMExcelGenerator
from server.workflow.agents.scope_agent.outputs.wbs_excel import WBSExcelGenerator
from server.workflow.agents.scope_agent.outputs.tailoring import TailoringGenerator
from server.workflow.agents.scope_agent.outputs.project_plan import ProjectPlanGenerator  # 신규 연결


logger = logging.getLogger("scope.agent")

# DB imports (optional)
try:
    from server.db.database import SessionLocal
    from server.db import pm_models
    _DB_AVAILABLE = True
except Exception as e:
    logger.warning("[ScopeAgent] DB import failed: %s", e)
    SessionLocal = None
    pm_models = None
    _DB_AVAILABLE = False

# --- LangChain v0.2+ 호환 import (fallback 포함) ---
try:
    from langchain_openai import OpenAIEmbeddings, AzureOpenAIEmbeddings
    from langchain_community.vectorstores import FAISS
except Exception:
    # 구버전 호환
    from langchain.embeddings import OpenAIEmbeddings  # type: ignore
    from langchain.vectorstores import FAISS  # type: ignore

# ---------------------------------------------------------------------
# LLM getter
# ---------------------------------------------------------------------
def get_llm():
    try:
        from server.utils.config import get_llm as _g
        llm = _g()
        logger.debug("[SCOPE_AGENT] get_llm() success: %s", getattr(llm, "__class__", llm))
        return llm
    except Exception as e:
        logger.warning("[SCOPE_AGENT] get_llm failed: %s", e)
        return None

# ---------------------------------------------------------------------
# 응답 텍스트 추출
# ---------------------------------------------------------------------
def _safe_extract_raw(resp: Any) -> str:
    """LLM 응답에서 실제 텍스트 추출(유연 처리)."""
    try:
        if resp is None:
            return ""
        
        # 이미 문자열인 경우 바로 반환 (가장 흔한 케이스)
        if isinstance(resp, str):
            logger.debug("[SCOPE] LLM 응답이 이미 문자열입니다")
            return resp
        
        # langchain/chat model-like: resp.generations / resp.generations[0].message.content
        if hasattr(resp, "generations"):
            gens = getattr(resp, "generations")
            try:
                # try to flatten common shapes
                if isinstance(gens, list) and len(gens) and hasattr(gens[0], "message"):
                    content = gens[0].message.content
                    logger.debug("[SCOPE] LLM 응답 추출: generations[0].message.content")
                    return content
            except Exception:
                pass
        
        # Azure / OpenAI-like: resp.choices[0].message.content or resp.choices[0].text
        if hasattr(resp, "choices"):
            c = resp.choices
            if isinstance(c, (list, tuple)) and len(c):
                first = c[0]
                if hasattr(first, "message"):
                    if hasattr(first.message, "get"):
                        content = first.message.get("content", "")
                    elif hasattr(first.message, "content"):
                        content = first.message.content
                    else:
                        content = str(first.message)
                    logger.debug("[SCOPE] LLM 응답 추출: choices[0].message")
                    return content
                if hasattr(first, "text"):
                    content = getattr(first, "text", "")
                    logger.debug("[SCOPE] LLM 응답 추출: choices[0].text")
                    return content
        
        # some SDKs use .content directly
        if hasattr(resp, "content"):
            content = getattr(resp, "content")
            logger.debug("[SCOPE] LLM 응답 추출: .content 속성")
            return content if isinstance(content, str) else str(content)
        
        # fallback to string conversion
        result = str(resp)
        logger.debug("[SCOPE] LLM 응답 추출: str() 변환")
        return result
    except Exception as e:
        logger.warning("[SCOPE] raw extract failed: %s", e)
        return str(resp) if resp else ""

# ---------------------------------------------------------------------
# JSON 파서 #1107
# ---------------------------------------------------------------------
def _json_from_text(maybe: str) -> Optional[dict]:
    """문자열에서 JSON 추출 (Markdown 코드 블록 지원)"""
    if not maybe:
        return None
    
    try:
        s = maybe.strip()
        
        # ⭐ Markdown 코드 블록 제거
        # ```json\n{...}\n``` → {...}
        s = re.sub(r'```json\s*', '', s)
        s = re.sub(r'```\s*', '', s)
        s = s.strip()
        
        # JSON 파싱
        if s.startswith("{") and s.endswith("}"):
            result = json.loads(s)
            req_count = len(result.get("requirements", []))
            logger.info(f"✅ [SCOPE] JSON 파싱 성공 (requirements={req_count})")
            return result
        
        # 정규식으로 추출
        m = re.search(r"(\{[\s\S]*\})", s)
        if m:
            result = json.loads(m.group(1))
            req_count = len(result.get("requirements", []))
            logger.info(f"✅ [SCOPE] 정규식 추출 성공 (requirements={req_count})")
            return result
            
    except json.JSONDecodeError as e:
        logger.error(f"[SCOPE] JSON 파싱 실패: {e}")
        logger.error(f"[SCOPE] 응답 처음 500자:\n{maybe[:500]}")
    except Exception as e:
        logger.error(f"[SCOPE] 예외: {e}")
    
    return None

# ============================================================================
# 1. _estimate_confidence 함수 수정 (Line 172-202) #1107 confidence 무시하고 파싱
# ============================================================================

def _estimate_confidence(resp_json: Optional[dict], raw_text: str) -> float:
    """
    개선된 confidence 추정기:
    - 요구사항이 없으면 매우 낮은 점수 (0.1)
    - 요구사항 수와 필드 완전성을 모두 고려
    - acceptance_criteria 존재 여부도 체크
    """
    if resp_json and isinstance(resp_json, dict):
        # direct provided confidence
        if "confidence" in resp_json:
            try:
                c = float(resp_json["confidence"])
                return min(max(c, 0.0), 1.0)
            except Exception:
                pass
        
        # heuristic: requirements 수와 품질
        reqs = resp_json.get("requirements")
        if not reqs or not isinstance(reqs, list):
            logger.debug("[SCOPE] confidence: requirements가 없거나 list가 아님")
            return 0.1  # 요구사항이 없으면 매우 낮은 점수
        
        if len(reqs) == 0:
            logger.debug("[SCOPE] confidence: requirements 배열이 비어있음")
            return 0.1  # 빈 배열도 매우 낮은 점수
        
        # 요구사항 수에 따른 기본 점수
        if len(reqs) < 3:
            base_score = 0.3  # 너무 적음
        elif len(reqs) < 5:
            base_score = 0.5  # 적음
        elif len(reqs) < 10:
            base_score = 0.6  # 보통
        else:
            base_score = 0.7  # 충분
        
        # 필드 완전성 체크
        filled = 0
        has_ac = 0  # acceptance_criteria 있는 것
        
        for r in reqs:
            # 필수 필드
            has_required = (
                r.get("req_id") and 
                r.get("title") and 
                r.get("description") and
                r.get("type") and
                r.get("priority")
            )
            
            if has_required:
                filled += 1
            
            # acceptance_criteria 체크
            ac = r.get("acceptance_criteria")
            if ac and isinstance(ac, list) and len(ac) >= 2:
                has_ac += 1
        
        if len(reqs) == 0:
            return 0.1
        
        field_ratio = filled / len(reqs)  # 필수 필드 충족률
        ac_ratio = has_ac / len(reqs)     # acceptance_criteria 충족률
        
        # 최종 점수 계산
        # base_score (0.3-0.7) + field_ratio (0-0.2) + ac_ratio (0-0.1)
        final_score = base_score + (field_ratio * 0.2) + (ac_ratio * 0.1)
        
        logger.debug(
            f"[SCOPE] confidence: {len(reqs)}개 요구사항, "
            f"필드 충족 {filled}/{len(reqs)}, "
            f"AC 충족 {has_ac}/{len(reqs)}, "
            f"점수 {final_score:.3f}"
        )
        
        return min(final_score, 0.99)
    
    # fallback: JSON 파싱 실패
    logger.debug("[SCOPE] confidence: JSON 파싱 실패")
    return 0.1

def _ensure_req_ids(reqs: List[dict]) -> List[dict]:
    """req_id가 없으면 자동 생성"""
    out = []
    ts = int(time.time())
    counter = 0
    for r in reqs:
        if not r.get("req_id"):
            counter += 1
            r["req_id"] = f"REQ-{ts}-{counter:02}"
        out.append(r)
    return out

# ---------------------------------------------------------------------
# 1111 PromptManager: RAG + 압축 + 캐싱
# ---------------------------------------------------------------------
class PromptManager:
    def __init__(self):
        self.llm = get_llm()
        self.vectorstore = None
        self._init_vectorstore()

    def _init_vectorstore(self):
        """ templates/ 및 rules 폴더를 벡터화. 키 없으면 RAG 비활성 """
        texts, metas = [], []
        for p in Path("templates").rglob("*.txt"):
            t = p.read_text(encoding="utf-8", errors="ignore")
            texts.append(t); metas.append({"name": str(p.relative_to("templates"))})
        for p in Path("rules").rglob("*.txt"):
            t = p.read_text(encoding="utf-8", errors="ignore")
            texts.append(t); metas.append({"name": str(p.relative_to("rules"))})
        if not texts: 
            logger.info("[PROMPT-RAG] 텍스트가 없어 RAG 생략")
            self.vectorstore = None    
            return
        
        # 1111 🔑 환경 변수 감지 (Azure 우선)
        azure_key = os.getenv("AZURE_OPENAI_API_KEY")
        azure_ep  = os.getenv("AZURE_OPENAI_ENDPOINT")
        azure_ver = os.getenv("OPENAI_API_VERSION") or os.getenv("AZURE_OPENAI_API_VERSION")
        azure_embed_deploy = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT")  # 예: text-embedding-3-large

        openai_key = os.getenv("OPENAI_API_KEY")
        try:
            if azure_key and azure_ep and azure_ver and azure_embed_deploy:
                emb = AzureOpenAIEmbeddings(
                    azure_endpoint=azure_ep,
                    api_key=azure_key,
                    api_version=azure_ver,
                    deployment=azure_embed_deploy,
                )
                logger.info("[PROMPT-RAG] AzureOpenAIEmbeddings 사용")
            elif openai_key:
                emb = OpenAIEmbeddings(  # langchain_openai
                    model=os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-large"),
                    api_key=openai_key,
                )
                logger.info("[PROMPT-RAG] OpenAIEmbeddings 사용")
            else:
                logger.warning("[PROMPT-RAG] 임베딩 키 없음 → RAG 비활성")
                self.vectorstore = None
                return

            self.vectorstore = FAISS.from_texts(texts, metadatas=metas, embedding=emb)
            logger.info(f"[PROMPT-RAG] 벡터스토어 초기화 완료 ({len(texts)} docs)")
        except Exception as e:
            logger.warning(f"[PROMPT-RAG] 초기화 실패 → RAG 비활성: {e}")
            self.vectorstore = None

    def build_rag_prompt(self, text: str, base_prompt=None, k=3) -> str:
        """사용자 문서와 의미적으로 유사한 템플릿/룰을 찾아 프롬프트 생성"""
        if not self.vectorstore:
            return base_prompt or build_scope_prompt(text)
        results = self.vectorstore.similarity_search(text, k=k)
        retrieved = "\n\n".join(r.page_content for r in results)
        base = base_prompt or "당신은 PMP 표준을 준수하는 PM 분석가입니다."
        if not self.vectorstore:
            # RAG 비활성 시에도 정상 동작
            return f"{base}\n\n문서:\n{text[:8000]}"
        results = self.vectorstore.similarity_search(text, k=k)
        retrieved = "\n\n".join(r.page_content for r in results)
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
    """RFP 문서로부터 Requirements/SRS/RTM/WBS(초안) 등을 생성하는 Agent
       추가 옵션 (payload['options']):
         - confidence_threshold: float (0..1), default=0.75
         - max_attempts: int, default=3
    """

    def __init__(self, data_dir: Optional[str] = None):
        self.llm = get_llm()
        self.pmgr = PromptManager()  # 1111
        self.data_dir = data_dir or "data"
        logger.info(f"[SCOPE_AGENT] 초기화 완료1 - data_dir: {self.data_dir}")

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
        project_id = payload.get("project_id") or payload.get("project_name") or "Unknown"
        text = payload.get("text") or ""
        documents = payload.get("documents") or []
        options = payload.get("options") or {}
        confidence_threshold = float(options.get("confidence_threshold", 0.75))
        max_attempts = int(options.get("max_attempts", 3))

        # if no text but documents - read first file path if exists (best-effort)
        if not text and documents:
            first = documents[0]
            path = None
            if isinstance(first, dict):
                path = first.get("path")
            else:
                path = getattr(first, "path", None)
            if path:
                p = Path(path)
                if not p.exists():
                    # maybe relative to data/inputs/RFP
                    alt = Path("data/inputs/RFP") / Path(path).name
                    if alt.exists():
                        p = alt
                if p.exists():
                    try:
                        # simple read for txt; for docx/pdf we expect upper layer to convert
                        text = p.read_text(encoding="utf-8", errors="ignore")
                    except Exception:
                        text = ""

        logger.info("🔵 [SCOPE] 요청: project_id=%s, methodology=%s", project_id, payload.get("methodology"))

        # Run extraction with confidence loop
        items, raw_resp = await self._extract_items_with_confidence(text, confidence_threshold, max_attempts)

        # Ensure req_ids
        reqs = items.get("requirements", [])
        if reqs:
            items["requirements"] = _ensure_req_ids(reqs)

        # Write outputs: srs, scope md, rtm csv, wbs json draft
        out_dir = Path("data/outputs/scope") / str(project_id)
        out_dir.mkdir(parents=True, exist_ok=True)

        srs_path = out_dir / f"{project_id}_SRS.md"
        self._generate_srs(project_id, items, srs_path)

        # WBS draft: keep simple hierarchical draft (could be improved via WBS synthesis step)
        wbs = await self._synthesize_wbs_draft(items, depth=int(options.get("wbs_depth", 3)))
        wbs_path = out_dir / "wbs_structure.json"
        wbs_path.write_text(json.dumps(wbs, ensure_ascii=False, indent=2), encoding="utf-8")

        # RTM csv
        rtm_csv = out_dir / "rtm.csv"
        with rtm_csv.open("w", encoding="utf-8", newline="") as fh:
            fh.write("req_id,wbs_id,test_case,verification_status\n")
            for r in items.get("requirements", []):
                fh.write(f"{r.get('req_id')},,,Candidate\n")

        # attempt DB save (best-effort)
        saved = 0
        if _DB_AVAILABLE:
            try:
                saved = self._save_requirements_db(project_id, items)
            except Exception as e:
                logger.exception("[SCOPE] DB save failed: %s", e)
                saved = 0
        else:
            logger.debug("[SCOPE] DB not available, skipping DB save")

        # PMP outputs (scope_statement excel etc.) - keep existing hooks
        pmp_outputs = await self._generate_pmp_outputs(project_id, items, wbs, options, out_dir)

        result = {
            "status": "ok",
            "project_id": project_id,
            "requirements": items.get("requirements", []),
            "functions": items.get("functions", []),
            "wbs_json": str(wbs_path),
            "wbs": wbs,
            "rtm_csv": str(rtm_csv),
            "srs_path": str(srs_path),
            "pmp_outputs": pmp_outputs,
            "db_saved_requirements": saved,
            "_llm_raw_response": str(raw_resp)[:2000],
        }
        logger.info("✅ [SCOPE] 응답완료: %s (requirements=%d, saved=%d)", project_id, len(items.get("requirements", [])), saved)
        return result


    def _fallback_extract(self, text: str) -> Dict[str, Any]:
        """간단 규칙 기반 (기존 fallback 유지)"""
        reqs = []
        funcs = []
        for i, ln in enumerate([l.strip() for l in text.splitlines() if l.strip()]):
            if re.search(r"(요구|필요|해야|shall|must|should)", ln, re.I):
                reqs.append({
                    "req_id": None,
                    "title": ln[:80],
                    "type": "functional",
                    "priority": "Medium",
                    "description": ln,
                    "source_span": f"line {i+1}"
                })
            if re.search(r"(기능|기능명|support|provide)", ln, re.I):
                funcs.append({"name": ln[:80], "desc": ln})
        logger.info("✅ [SCOPE] fallback 추출: %d reqs, %d funcs", len(reqs), len(funcs))
        return {"requirements": reqs, "functions": funcs}

    async def _synthesize_wbs_draft(self, items: Dict[str, Any], depth: int = 3) -> Dict[str, Any]:
        """간단한 WBS 초안 생성 (기존 로직 유지)"""
        nodes = [{
            "id": "WBS-1",
            "name": "Project",
            "level": 1,
            "children": []
        }]
        phases = []
        reqs = items.get("requirements", [])
        # naive: split into phases of ~ceil(len(reqs)/3)
        if reqs:
            per = max(1, (len(reqs) + 2) // 3)
            for i in range(3):
                start = i * per
                seg = reqs[start:start+per]
                phase = {
                    "id": f"WBS-1.{i+1}",
                    "name": f"Phase {i+1}",
                    "level": 2,
                    "children": []
                }
                # tasks per requirement
                for j, r in enumerate(seg, 1):
                    phase["children"].append({
                        "id": f"{phase['id']}.{j}",
                        "name": r.get("title", f"Task {i+1}.{j}")[:60],
                        "level": 3,
                        "owner": None,
                        "deliverables": None
                    })
                phases.append(phase)
        else:
            # default phases
            for i in range(3):
                phases.append({
                    "id": f"WBS-1.{i+1}",
                    "name": f"Phase {i+1}",
                    "level": 2,
                    "children": []
                })
        nodes[0]["children"] = phases
        return {"nodes": nodes, "depth": depth}

    def _save_requirements_db(self, project_id: str, items: Dict[str, Any]) -> int:
        """
        DB에 요구사항 저장(간단 구현). 반환: 저장된 레코드 수.
        안전 장치: req_id가 비어있으면 자동생성 후 저장.
        """
        if not _DB_AVAILABLE:
            logger.debug("[SCOPE] DB not available")
            return 0
        db = SessionLocal()
        saved = 0
        try:
            reqs = items.get("requirements", []) or []
            for r in reqs:
                req_id = r.get("req_id")
                title = r.get("title") or r.get("description")[:200]
                description = r.get("description")
                rtype = r.get("type") or r.get("category") or "functional"
                priority = r.get("priority") or "Medium"
                source_doc = r.get("source_span") or None

                if not req_id:
                    req_id = f"AUTO-{int(time.time())}-{saved+1}"
                    logger.debug("[SCOPE] 자동 req_id 생성: %s", req_id)

                # upsert-like: try find existing by project_id + req_id
                existing = db.query(pm_models.PM_Requirement).filter_by(project_id=project_id, req_id=req_id).first()
                if existing:
                    existing.title = title
                    existing.description = description
                    existing.priority = priority
                    existing.type = rtype
                    existing.source_doc = source_doc
                else:
                    obj = pm_models.PM_Requirement(
                        project_id=project_id,
                        req_id=req_id,
                        title=title,
                        description=description,
                        priority=priority,
                        status="new",
                        source_doc=source_doc,
                        created_at=datetime.utcnow()
                    )
                    db.add(obj)
                saved += 1
            db.commit()
            logger.info("[SCOPE] DB 저장 완료: %d 레코드", saved)
            return saved
        except Exception as e:
            logger.exception("[SCOPE] Saving to DB failed: %s", e)
            try:
                db.rollback()
            except Exception:
                pass
            return 0
        finally:
            db.close()

    # SRS / Charter / PMP outputs (existing hooks)
    def _generate_srs(self, project_id: Any, items: Dict[str, Any], out_path: Path):
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(f"# Software Requirements Specification\n")
            f.write(f"**Project:** {project_id}\n")
            f.write(f"**Generated:** {datetime.utcnow().isoformat()}\n\n")
            f.write("## 1. Requirements\n\n")
            for r in items.get("requirements", []):
                f.write(f"### {r.get('req_id')}: {r.get('title')}\n")
                f.write(f"- **Type:** {r.get('type')}\n")
                f.write(f"- **Priority:** {r.get('priority')}\n")
                f.write(f"- **Description:** {r.get('description')}\n")
                f.write(f"- **Source:** {r.get('source_span')}\n\n")
        return str(out_path)

    # def _generate_pmp_outputs(self, project_id: Any, project_dir: Path, requirements: Dict[str, Any]) -> Dict[str, Optional[str]]:
    #     outputs = {}
    #     try:
    #         from .outputs.scope_statement import ScopeStatementGenerator
    #         scp = project_dir / f"{project_id}_ScopeStatement.xlsx"
    #         outputs["scope_statement_excel"] = ScopeStatementGenerator.generate(project_id, requirements, scp)
    #     except Exception as e:
    #         outputs["scope_statement_excel"] = None
    #         logger.debug("ScopeStatementGenerator not available: %s", e)
    #     return outputs
    async def _generate_pmp_outputs(self, project_id: str, items: dict, wbs_data: dict, options: dict, out_dir: Path):
        """Scope 분석 결과를 기반으로 실제 문서 산출물 생성"""
        try:
            reqs = items.get("requirements", [])
            logger.info(f"[SCOPE] 📦 산출물 생성 시작 - {len(reqs)}개 요구사항")
            req_summary = "\n".join([
                f"- {r['req_id']}: {r['title']} ({r['type']}, {r['priority']})"
                for r in reqs[:10]
            ])
            charter_base = PROJECT_CHARTER_PROMPT.format(
                project_name=project_id,
                sponsor=options.get("sponsor", "미정"),
                background=options.get("background", "회사 내부 요청"),
                objectives=options.get("objectives", "명확한 요구사항 도출 및 시스템 품질 확보"),
                requirements_summary=req_summary
            )
            # 1️⃣ 프로젝트 헌장 (Word)
            charter_path = out_dir / f"{project_id}_프로젝트헌장.docx"
            ProjectCharterGenerator.generate(
                project_name=project_id,
                requirements=reqs,
                wbs_data=wbs_data,
            )
            logger.info(f"[SCOPE] ✅ 프로젝트 헌장 생성: {charter_path}")

            # 2️⃣ 범위 기술서 (Excel)
            scope_stmt_path = out_dir / f"{project_id}_범위기술서.xlsx"
            ScopeStatementGenerator.generate(
                project_name=project_id,
                wbs_data=wbs_data,
                requirements=reqs,
                output_path=scope_stmt_path
            )
            logger.info(f"[SCOPE] ✅ 범위 기술서 생성: {scope_stmt_path}")

            # 3️⃣ 요구사항 추적표 (RTM)
            rtm_path = out_dir / f"{project_id}_요구사항추적표.xlsx"
            RTMExcelGenerator.generate(
                requirements=reqs,
                output_path=rtm_path
            )
            logger.info(f"[SCOPE] ✅ RTM 생성: {rtm_path}")

            # 4️⃣ WBS Excel
            wbs_excel_path = out_dir / f"{project_id}_WBS.xlsx"
            WBSExcelGenerator.generate(
                wbs_data=wbs_data,
                output_path=wbs_excel_path
            )
            logger.info(f"[SCOPE] ✅ WBS Excel 생성: {wbs_excel_path}")

            # 5️⃣ Tailoring (방법론별)
            tailoring_path = out_dir / f"{project_id}_테일러링.xlsx"
            TailoringGenerator.generate(
                methodology=options.get("methodology", "waterfall"),
                requirements=reqs, 
                output_path=tailoring_path
            )
            logger.info(f"[SCOPE] ✅ Tailoring 생성: {tailoring_path}")

            # 6️⃣ 사업수행계획서 (Project Plan)
            plan_path = out_dir / f"{project_id}_사업수행계획서.xlsx"
            ProjectPlanGenerator.generate(
                project_name=project_id,
                requirements=reqs,
                wbs_data=wbs_data,
                options=options,
                output_path=plan_path
            )
            logger.info(f"[SCOPE] ✅ 사업수행계획서 생성: {plan_path}")

        except Exception as e:
            logger.error(f"[SCOPE] ❌ 산출물 생성 중 오류: {e}")
        

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

    async def _generate_project_documents(self, project_id: str, options: dict, out_dir: Path):
        """
        요구사항 기반 Project Charter, Tailoring Guide, WBS 문서를 생성
        """
        logger.info(f"[SCOPE] 📄 Project Charter / Tailoring / WBS 생성 시작")

        # 요구사항 파일 로드
        req_path = out_dir / "requirements.json"
        req_json = {}
        if req_path.exists():
            try:
                req_json = json.loads(req_path.read_text(encoding="utf-8"))
            except Exception as e:
                logger.warning(f"[SCOPE] 요구사항 JSON 로드 실패: {e}")

        # 1️⃣ Charter 생성
        try:
            charter_base = PROJECT_CHARTER_PROMPT.format(
                project_name=project_id,
                sponsor=options.get("sponsor", "미정"),
                background=options.get("background", "회사 내부 요청"),
                objectives=options.get("objectives", "명확한 요구사항 도출 및 시스템 품질 확보")
            )
            charter_prompt = self.pmgr.build_rag_prompt(charter_base)
            charter_prompt = self.pmgr.compress_prompt(charter_prompt)

            resp = await asyncio.to_thread(
                self.llm.invoke,
                [
                    {"role": "system", "content": "You are a PMO documentation expert."},
                    {"role": "user", "content": charter_prompt}
                ]
            )
            charter_text = _safe_extract_raw(resp)
            (out_dir / "project_charter.md").write_text(charter_text, encoding="utf-8")
            logger.info(f"[SCOPE] ✅ Project Charter 생성 완료")
        except Exception as e:
            logger.warning(f"[SCOPE] ⚠️ Charter 생성 실패: {e}")

        # 2️⃣ Tailoring Guide 생성
        try:
        # 1111
            func_count = len([r for r in reqs if r["type"] == "functional"])
            nonfunc_count = len([r for r in reqs if r["type"] == "non-functional"])
            constraint_count = len([r for r in reqs if r["type"] == "constraint"])
            tailoring_base = TAILORING_PROMPT.format(
                req_count=len(reqs),
                func_count=func_count,
                nonfunc_count=nonfunc_count,
                constraint_count=constraint_count,
                size=options.get("size", "중형"),
                methodology=options.get("methodology", "Waterfall"),
                complexity=options.get("complexity", "중간"),
                team_size=options.get("team_size", "8"),
                duration=options.get("duration", "6")
)
            tailoring_prompt = self.pmgr.build_rag_prompt(tailoring_base)
            tailoring_prompt = self.pmgr.compress_prompt(tailoring_prompt)

            resp = await asyncio.to_thread(
                self.llm.invoke,
                [
                    {"role": "system", "content": "You are a PMP process tailoring expert."},
                    {"role": "user", "content": tailoring_prompt}
                ]
            )
            tailoring_text = _safe_extract_raw(resp)
            (out_dir / "tailoring_guide.json").write_text(tailoring_text, encoding="utf-8")
            logger.info(f"[SCOPE] ✅ Tailoring Guide 생성 완료")
        except Exception as e:
            logger.warning(f"[SCOPE] ⚠️ Tailoring 생성 실패: {e}")

        # 3️⃣ 요구사항 기반 WBS 생성
        try:
            from server.workflow.agents.schedule_agent.prompts import WBS_SYNTH_PROMPT

            if req_json.get("requirements"):
                req_text = json.dumps(req_json["requirements"][:20], ensure_ascii=False, indent=2)
                wbs_prompt = WBS_SYNTH_PROMPT.format(requirements_json=req_text)
                wbs_prompt = self.pmgr.build_rag_prompt(wbs_prompt)
                wbs_prompt = self.pmgr.compress_prompt(wbs_prompt)

                resp = await asyncio.to_thread(
                    self.llm.invoke,
                    [
                        {"role": "system", "content": "You are a project scheduling expert."},
                        {"role": "user", "content": wbs_prompt}
                    ]
                )
                wbs_raw = _safe_extract_raw(resp)
                match = re.search(r"(\{[\s\S]*\})", wbs_raw)
                if match:
                    wbs_json = json.loads(match.group(1))
                    (out_dir / "wbs_structure.json").write_text(
                        json.dumps(wbs_json, ensure_ascii=False, indent=2), encoding="utf-8"
                    )
                    logger.info(f"[SCOPE] ✅ WBS 구조 생성 완료: {len(wbs_json.get('nodes', []))}개 노드")
        except Exception as e:
            logger.warning(f"[SCOPE] ⚠️ WBS 생성 실패: {e}")

        logger.info(f"[SCOPE] 📦 Project 문서 생성 완료: {project_id}")


# ---------------------------------------------------------------------
# 체인 파이프라인 (Scope → Quality → Schedule)
# ---------------------------------------------------------------------
class ScopeChainPipeline:
    def __init__(self, scope_agent, quality_agent, schedule_agent):
        self.scope_agent = scope_agent
        self.quality_agent = quality_agent
        self.schedule_agent = schedule_agent

    async def run(self, text, project_meta=None):
        logger.info("🚀 체인 파이프라인 시작")

        # 1️⃣ Scope 추출 (RAG + Few-shot)
        scope_res = await self.scope_agent._extract_items_with_confidence(text)
        reqs = scope_res[0].get("requirements", [])
        logger.info(f"📄 요구사항 추출 완료: {len(requirements)}개")
        
        # 2️⃣ 품질 검증
        valid = self.quality_agent.validate(reqs, text, project_meta)
        logger.info(f"✅ 품질 점수: {validation['score']} ({validation['grade']})")

        if not valid.get("pass", True):
            # 자동 개선 루프
            logger.info("🔄 품질 미달 → 재추출 시도")
            reqs = self.scope_agent.refine_requirements(text, reqs, valid, project_meta)
        
        # 3️⃣ 스케줄 초안 (ScheduleAgent 연동)
        wbs = await self.schedule_agent.generate_wbs(reqs)
        logger.info(f"📅 WBS 생성 완료: {len(wbs_draft.get('nodes', []))}단계")
        return {"requirements": reqs, "validation": valid, "wbs": wbs, "status": "complete"}

        # 4 Output 생성 
        wbs = await self.schedule_agent.generate_wbs(reqs)
        logger.info(f"📅 WBS 생성 완료: {len(wbs_draft.get('nodes', []))}단계")
        return {"requirements": reqs, "validation": valid, "wbs": wbs, "status": "complete"}


    # ScopeAgent에 추가할 메서드들
    # pipeline.py의 ScopeAgent 클래스에 추가

    def refine_requirements(self, 
                        text: str, 
                        previous_result: List[Dict[str, Any]],
                        validation_result: Dict[str, Any],
                        project_meta: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        검증 피드백을 반영한 요구사항 재추출
        
        Args:
            text: 원본 문서
            previous_result: 이전 추출 결과
            validation_result: 품질 검증 결과
            project_meta: 프로젝트 메타데이터
        
        Returns:
            개선된 요구사항 리스트
        """
        logger.info("[SCOPE] 피드백 기반 재추출 시작")
        
        # 검증 결과 분석
        score = validation_result.get('score', 0)
        issues = validation_result.get('issues', [])
        missing = validation_result.get('missing_requirements', [])
        recommendations = validation_result.get('recommendations', [])
        
        logger.info(f"[SCOPE] 이전 점수: {score}")
        logger.info(f"[SCOPE] 이슈: {len(issues)}개")
        logger.info(f"[SCOPE] 누락: {len(missing)}개")
        
        # 피드백 프롬프트 생성
        feedback_section = self._build_feedback_section(
            score, issues, missing, recommendations
        )
        
        # 개선된 프롬프트 생성
        refinement_prompt = f"""
    당신은 PMP 표준을 준수하는 전문 PMO 분석가입니다.

    ## 🔄 요구사항 개선 작업

    ### 이전 추출 결과
    추출된 요구사항: {len(previous_result)}개
    품질 점수: {score}/100

    ### 📋 이전 추출 결과 (요약)
    {self._summarize_requirements(previous_result)}

    ### ⚠️ 검증에서 발견된 문제점

    {feedback_section}

    ### 🎯 개선 지침

    1. **누락된 요구사항 추가**
    {self._format_missing(missing)}

    2. **기존 요구사항 개선**
    {self._format_issues(issues)}

    3. **권장사항 반영**
    {self._format_recommendations(recommendations)}

    ### 📝 개선 원칙

    - 모호한 표현 제거: "적절히", "충분히" → 구체적 기준
    - 측정 가능성: 모든 요구사항에 정량적 기준 포함
    - acceptance_criteria: 최소 3개 이상, 각각 검증 가능
    - 세분화: 하나의 요구사항 = 하나의 기능

    ---

    ## 📄 원문 문서
    {text[:6000]}

    ---

    위 피드백을 반영하여 요구사항을 개선하세요.
    기존 요구사항은 유지하되, 문제가 있는 부분은 수정하고, 누락된 부분은 추가하세요.

    출력 JSON:
    {{{{
    "requirements": [
        {{{{
        "req_id": "REQ-001",
        "title": "...",
        "type": "functional",
        "priority": "High",
        "description": "...",
        "source_span": "...",
        "acceptance_criteria": [...]
        }}}}
    ]
    }}}}
    """
        
        # LLM 호출
        try:
            messages = [
                {"role": "system", "content": "You are a PM analyst expert in requirements refinement."},
                {"role": "user", "content": refinement_prompt}
            ]
            
            logger.info("[SCOPE] LLM 재추출 호출")
            resp = self.llm.invoke(messages)
            content = _safe_extract_raw(resp)
            
            logger.info(f"[SCOPE] 응답 길이: {len(content)}")
            
            # JSON 파싱
            json_text = _json_first(content)
            if not json_text:
                logger.warning("[SCOPE] JSON 추출 실패, 이전 결과 반환")
                return previous_result
            
            result = _postprocess(json_text, text)
            
            logger.info(f"[SCOPE] 재추출 완료: {len(result)}개 요구사항")
            
            return result
            
        except Exception as e:
            logger.error(f"[SCOPE] 재추출 실패: {e}")
            return previous_result


    def _build_feedback_section(self, score, issues, missing, recommendations):
        """피드백 섹션 생성"""
        
        sections = []
        
        # 점수 및 등급
        if score < 60:
            grade = "Poor"
            emoji = "❌"
        elif score < 75:
            grade = "Fair"
            emoji = "⚠️"
        elif score < 90:
            grade = "Good"
            emoji = "✅"
        else:
            grade = "Excellent"
            emoji = "🌟"
        
        sections.append(f"{emoji} 품질 등급: {grade} ({score}/100)")
        
        # 이슈
        if issues:
            sections.append(f"\n**발견된 이슈 ({len(issues)}개):**")
            for i, issue in enumerate(issues[:10], 1):
                sections.append(f"{i}. {issue}")
        
        # 누락
        if missing:
            sections.append(f"\n**누락된 요구사항 ({len(missing)}개):**")
            for i, miss in enumerate(missing[:5], 1):
                sections.append(f"{i}. {miss}")
        
        # 권장사항
        if recommendations:
            sections.append(f"\n**개선 권장사항 ({len(recommendations)}개):**")
            for i, rec in enumerate(recommendations[:5], 1):
                sections.append(f"{i}. {rec}")
        
        return "\n".join(sections)


    def _summarize_requirements(self, requirements):
        """요구사항 요약"""
        
        if not requirements:
            return "없음"
        
        summary = []
        for req in requirements[:10]:
            summary.append(
                f"- {req.get('req_id')}: {req.get('title')} "
                f"({req.get('type')}, {req.get('priority')})"
            )
        
        if len(requirements) > 10:
            summary.append(f"... 외 {len(requirements) - 10}개")
        
        return "\n".join(summary)


    def _format_missing(self, missing):
        """누락 항목 포맷팅"""
        
        if not missing:
            return "없음"
        
        formatted = []
        for i, miss in enumerate(missing, 1):
            formatted.append(f"   {i}. {miss}")
        
        return "\n".join(formatted)


    def _format_issues(self, issues):
        """이슈 포맷팅"""
        
        if not issues:
            return "없음"
        
        formatted = []
        for i, issue in enumerate(issues[:10], 1):
            formatted.append(f"   {i}. {issue}")
        
        return "\n".join(formatted)


    def _format_recommendations(self, recommendations):
        """권장사항 포맷팅"""
        
        if not recommendations:
            return "없음"
        
        formatted = []
        for i, rec in enumerate(recommendations[:5], 1):
            formatted.append(f"   {i}. {rec}")
        
        return "\n".join(formatted)


    # ============================================================================
    # extract_with_validation 함수 개선 버전
    # ============================================================================

    def extract_with_validation_v2(scope_agent, 
                                quality_agent,
                                text: str, 
                                project_meta: Optional[Dict] = None,
                                max_attempts: int = 3,
                                strategy: str = "auto") -> Dict[str, Any]:
        """
        검증 기반 요구사항 추출 (개선 버전)
        
        Args:
            scope_agent: ScopeAgent 인스턴스
            quality_agent: QualityAgent 인스턴스
            text: 원본 문서
            project_meta: 프로젝트 메타데이터
            max_attempts: 최대 시도 횟수
            strategy: 재추출 전략 ("auto", "feedback", "staged", "examples")
        
        Returns:
            {
                "success": bool,
                "requirements": [...],
                "validation": {...},
                "attempts": int,
                "improvements": [...],
                "history": [...]
            }
        """
        logger.info(f"\n{'='*70}")
        logger.info(f"🚀 검증 기반 추출 프로세스 시작 (개선 버전)")
        logger.info(f"📝 문서 길이: {len(text)} 문자")
        logger.info(f"🔄 최대 시도: {max_attempts}회")
        logger.info(f"📋 전략: {strategy}")
        logger.info(f"{'='*70}\n")
        
        history = []
        improvements = []
        previous_result = None
        validation_result = None
        
        for attempt in range(1, max_attempts + 1):
            logger.info(f"\n{'─'*70}")
            logger.info(f"📝 시도 #{attempt}/{max_attempts}")
            logger.info(f"{'─'*70}")
            
            # 1. 요구사항 추출
            if attempt == 1:
                # 첫 시도: 일반 추출
                logger.info("🔍 초기 추출 수행")
                result = scope_agent.analyze_rfp(text, project_meta)
                method = "initial"
            else:
                # 재시도: 피드백 반영 재추출
                logger.info(f"🔄 피드백 기반 재추출 수행")
                logger.info(f"   이전 점수: {validation_result['score']:.1f}")
                logger.info(f"   이슈: {len(validation_result['issues'])}개")
                logger.info(f"   누락: {len(validation_result['missing_requirements'])}개")
                
                # refine_requirements 메서드 호출
                result = scope_agent.refine_requirements(
                    text, 
                    previous_result, 
                    validation_result,
                    project_meta
                )
                method = "refined"
            
            # 결과 정규화
            requirements = result if isinstance(result, list) else result.get('requirements', [])
            logger.info(f"✅ {len(requirements)}개 요구사항 추출 완료")
            
            # 2. 품질 검증
            logger.info("🔍 품질 검증 시작")
            validation_result = quality_agent.validate(requirements, text, project_meta)
            
            current_score = validation_result['score']
            logger.info(f"🎯 점수: {current_score:.1f} ({validation_result['grade']})")
            
            # 개선도 계산
            if previous_result:
                prev_score = history[-1]['validation']['score']
                improvement = current_score - prev_score
                improvements.append(improvement)
                logger.info(f"📈 개선도: {improvement:+.1f}점")
            
            # 히스토리 저장
            history.append({
                "attempt": attempt,
                "method": method,
                "requirements_count": len(requirements),
                "validation": validation_result,
                "timestamp": datetime.now().isoformat()
            })
            
            # 3. 통과 여부 확인
            if validation_result['pass']:
                logger.info(f"\n{'='*70}")
                logger.info(f"✅ 검증 통과! (시도 {attempt}회)")
                logger.info(f"🎯 최종 점수: {current_score:.1f}")
                logger.info(f"🏆 등급: {validation_result['grade']}")
                
                if attempt > 1:
                    total_improvement = current_score - history[0]['validation']['score']
                    logger.info(f"📈 총 개선: {total_improvement:+.1f}점")
                
                logger.info(f"{'='*70}\n")
                
                return {
                    "success": True,
                    "requirements": requirements,
                    "validation": validation_result,
                    "attempts": attempt,
                    "method": method,
                    "improvements": improvements,
                    "history": history,
                    "message": f"검증 통과 (시도 {attempt}회, 최종 점수 {current_score:.1f})"
                }
            
            # 검증 실패
            logger.warning(f"\n⚠️ 검증 미통과")
            logger.warning(f"   점수: {current_score:.1f} (기준: {quality_agent.threshold})")
            logger.warning(f"   등급: {validation_result['grade']}")
            
            if validation_result['issues']:
                logger.warning(f"\n📋 주요 이슈:")
                for i, issue in enumerate(validation_result['issues'][:5], 1):
                    logger.warning(f"   {i}. {issue}")
            
            if validation_result['missing_requirements']:
                logger.warning(f"\n📋 누락 항목:")
                for i, miss in enumerate(validation_result['missing_requirements'][:3], 1):
                    logger.warning(f"   {i}. {miss}")
            
            # 마지막 시도 전 경고
            if attempt == max_attempts - 1:
                logger.warning(f"\n⚠️ 마지막 시도 전입니다!")
            
            previous_result = requirements
        
        # 최대 시도 횟수 초과
        final_score = validation_result['score']
        logger.error(f"\n{'='*70}")
        logger.error(f"❌ {max_attempts}회 시도 후에도 검증 기준 미달")
        logger.error(f"   최종 점수: {final_score:.1f} (기준: {quality_agent.threshold})")
        logger.error(f"   최종 등급: {validation_result['grade']}")
        
        if improvements:
            avg_improvement = sum(improvements) / len(improvements)
            logger.error(f"   평균 개선: {avg_improvement:+.1f}점/시도")
        
        logger.error(f"{'='*70}\n")
        
        return {
            "success": False,
            "requirements": requirements,
            "validation": validation_result,
            "attempts": max_attempts,
            "method": method,
            "improvements": improvements,
            "history": history,
            "message": f"품질 기준 미달 (최종 {final_score:.1f}점)"
        }


