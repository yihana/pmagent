from __future__ import annotations
import os
import re
import json
import asyncio
import time
import logging
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("scope.agent")

# prompts import (fallbacks provided)
try:
    from .prompts import SCOPE_EXTRACT_PROMPT, RTM_PROMPT, WBS_SYNTHESIS_PROMPT
except Exception:
    logger.warning("[SCOPE_AGENT] prompts import failed, using fallback prompts.")
    SCOPE_EXTRACT_PROMPT = """
당신은 PMP 표준을 준수하는 PMO 분석가입니다.
아래 문서에서 요구사항(requirements), 관련 기능(functions), 산출물(deliverables), 승인기준(acceptance_criteria)을 구조화하여 JSON으로 추출하세요.
요구사항은 고유 아이디(req_id)를 부여하세요 (예: REQ-001).
출력 예시:
{{
  "requirements":[{{"req_id":"REQ-001","title":"...","type":"functional","priority":"High","description":"...","source_span":"..."}}],
  "functions": [],
  "deliverables": [],
  "acceptance_criteria": []
}}
문서:
{context}
"""
    RTM_PROMPT = "RTM mapping for requirements: {{requirements}}"
    WBS_SYNTHESIS_PROMPT = "WBS synthesis for items: {{items}}"

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

# LLM getter (uses server.utils.config.get_llm if present)
def get_llm():
    try:
        from server.utils.config import get_llm as _g
        llm = _g()
        logger.debug("[SCOPE_AGENT] get_llm() success: %s", getattr(llm, "__class__", llm))
        return llm
    except Exception as e:
        logger.warning("[SCOPE_AGENT] get_llm failed: %s", e)
        return None

# ------- Helpers -------

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

def _json_from_text(maybe: str) -> Optional[dict]:
    """문자열에서 최초 JSON 객체(중괄호)를 추출해 파싱 시도."""
    if not maybe:
        return None
    try:
        # attempt to find JSON object, prefer full content if it's JSON
        s = maybe.strip()
        if s.startswith("{") and s.endswith("}"):
            return json.loads(s)
        m = re.search(r"(\{[\s\S]*\})", maybe)
        if m:
            return json.loads(m.group(1))
    except Exception as e:
        logger.debug("[SCOPE] json parse failed: %s", e)
    return None

def _estimate_confidence(resp_json: Optional[dict], raw_text: str) -> float:
    """
    간단한 confidence 추정기:
    - LLM이 'confidence' 키(0..1)를 반환하면 우선 사용
    - 아니면 요구사항/기능 수, 각 요구사항의 필드 완전성 등을 기준으로 0..1 추정
    """
    if resp_json and isinstance(resp_json, dict):
        # direct provided confidence
        if "confidence" in resp_json:
            try:
                c = float(resp_json["confidence"])
                return min(max(c, 0.0), 1.0)
            except Exception:
                pass
        # heuristic: presence of requirements and fields
        reqs = resp_json.get("requirements") if resp_json else None
        if reqs and isinstance(reqs, list) and len(reqs) > 0:
            score = 0.5
            filled = 0
            for r in reqs:
                if r.get("req_id") and r.get("title") and r.get("description"):
                    filled += 1
            ratio = filled / len(reqs)
            score += 0.5 * ratio  # 0.5 ~ 1.0
            return min(score, 0.99)
    # fallback: if raw_text length small -> low confidence, else medium
    if raw_text and len(raw_text) > 800:
        return 0.6
    if raw_text and len(raw_text) > 200:
        return 0.45
    return 0.2

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

# ------- ScopeAgent -------

class ScopeAgent:
    """RFP 문서로부터 Requirements/SRS/RTM/WBS(초안) 등을 생성하는 Agent
       추가 옵션 (payload['options']):
         - confidence_threshold: float (0..1), default=0.75
         - max_attempts: int, default=3
    """

    def __init__(self, data_dir: Optional[str] = None):
        self.llm = get_llm()
        self.data_dir = data_dir or "data"
        logger.info(f"[SCOPE_AGENT] 초기화 완료 - data_dir: {self.data_dir}")

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
        pmp_outputs = self._generate_pmp_outputs(project_id, out_dir, items)

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

    async def _extract_items_with_confidence(self, text: str, threshold: float, max_attempts: int):
        """
        LLM을 반복 호출하여 confidence가 threshold 이상일 때까지 재시도.
        반환: (items_dict, raw_response)
        """
        if not text:
            return {"requirements": [], "functions": []}, None

        llm = self.llm
        attempt = 0
        prev_raw = None
        last_items = None
        last_raw = None

        while attempt < max_attempts:
            attempt += 1
            logger.info("🔵 [SCOPE] LLM 시도 #%d (threshold=%.2f)", attempt, threshold)

            # build prompt - include previous output for refinement if present
            if last_items is None:
                prompt = SCOPE_EXTRACT_PROMPT.format(context=text[:8000])
            else:
                # refinement prompt: ask to improve/clarify previous JSON
                prompt = (
                    "이전 출력을 개선하세요. 이전 출력(JSON):\n"
                    f"{json.dumps(last_items, ensure_ascii=False, indent=2)}\n\n"
                    "원문 문서:\n"
                    f"{text[:4000]}\n\n"
                    "요청: 누락/중복/잘못 매핑된 요구사항을 수정하고, 각 요구사항에 req_id/title/description/type/priority/source_span을 제공하세요. "
                    "최종 결과는 JSON으로만 반환하세요."
                )

            raw_resp = None
            parsed = None
            try:
                if llm:
                    # flexible invocation - supports sync/async SDKs via to_thread
                    def call():
                        try:
                            if hasattr(llm, "generate"):
                                logger.debug("[SCOPE] LLM 호출: generate() 메서드 사용")
                                return llm.generate(prompt)
                            if callable(llm):
                                logger.debug("[SCOPE] LLM 호출: callable 직접 호출")
                                return llm(prompt)
                            if hasattr(llm, "invoke"):
                                logger.debug("[SCOPE] LLM 호출: invoke() 메서드 사용")
                                return llm.invoke(prompt)
                            logger.warning("[SCOPE] LLM 호출 방법을 찾을 수 없음")
                            return llm  # unlikely
                        except Exception as e:
                            logger.error(f"[SCOPE] LLM 호출 중 예외: {e}")
                            raise

                    logger.info(f"🤖 [SCOPE] LLM 호출 시작 (프롬프트 길이: {len(prompt)})")
                    resp = await asyncio.to_thread(call)
                    logger.info(f"✅ [SCOPE] LLM 응답 수신 (타입: {type(resp).__name__})")
                    
                    raw_resp = _safe_extract_raw(resp)
                    logger.info(f"📄 [SCOPE] 응답 텍스트 추출 완료 (길이: {len(str(raw_resp))})")
                    logger.debug(f"[SCOPE] 응답 내용 (처음 500자):\n{str(raw_resp)[:500]}")
                else:
                    logger.warning("[SCOPE] LLM 미설정, fallback 사용")
                    return self._fallback_extract(text), None
            except Exception as e:
                logger.warning("🟠 [SCOPE] LLM 호출 실패: %s", e)
                logger.debug(f"[SCOPE] 실패 상세:\n{traceback.format_exc()}")
                # fallback to rule extraction if first attempt fails
                if attempt == max_attempts:
                    return self._fallback_extract(text), None
                last_items = None
                last_raw = str(e)
                continue

            # try parse JSON from raw_resp
            parsed = _json_from_text(raw_resp)
            confidence = _estimate_confidence(parsed, raw_resp)
            logger.info("🔵 [SCOPE] parsed=%s, estimated_confidence=%.3f", bool(parsed), confidence)

            if parsed and confidence >= threshold:
                logger.info("✅ [SCOPE] confidence threshold met (%.3f >= %.3f) on attempt %d", confidence, threshold, attempt)
                return parsed, raw_resp

            # If parsed but confidence low, set last_items to parsed and re-prompt for refinement
            if parsed:
                last_items = parsed
                last_raw = raw_resp
                # continue loop to refine
                logger.info("[SCOPE] 재시도: parsed but low confidence (%.3f). 재프롬프트 진행...", confidence)
                await asyncio.sleep(0.2)  # small backoff
                continue

            # If not parsed (no JSON), provide guidance and try again
            logger.info("[SCOPE] JSON 파싱 실패 혹은 포맷 오류 — 재시도합니다 (attempt %d)", attempt)
            # create a clarifying prompt forcing JSON output
            last_items = None
            last_raw = raw_resp
            await asyncio.sleep(0.2)
            continue

        # after attempts exhausted, fallback to parsed if any, else rule-based
        if last_items:
            logger.warning("[SCOPE] 최대 시도(%d) 도달: 마지막 parsed 사용 (confidence %.3f)", max_attempts, _estimate_confidence(last_items, last_raw))
            return last_items, last_raw
        logger.warning("[SCOPE] 최대 시도(%d) 도달: fallback 규칙 기반 사용", max_attempts)
        return self._fallback_extract(text), last_raw

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

    def _generate_pmp_outputs(self, project_id: Any, project_dir: Path, requirements: Dict[str, Any]) -> Dict[str, Optional[str]]:
        outputs = {}
        try:
            from .outputs.scope_statement import ScopeStatementGenerator
            scp = project_dir / f"{project_id}_ScopeStatement.xlsx"
            outputs["scope_statement_excel"] = ScopeStatementGenerator.generate(project_id, requirements, scp)
        except Exception as e:
            outputs["scope_statement_excel"] = None
            logger.debug("ScopeStatementGenerator not available: %s", e)
        return outputs