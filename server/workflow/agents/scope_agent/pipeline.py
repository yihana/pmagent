# server/workflow/agents/scope_agent/pipeline.py
# 수정판 — LLM 안전 파싱, req_id 자동 생성, DB 직렬화 강화 포함

import json
import asyncio
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime

# 로거
import logging
logger = logging.getLogger("scope.agent")

def _find_root(start: Path) -> Path:
    """프로젝트 루트 찾기 (data 폴더가 있는 위치)"""
    for p in start.parents:
        if (p / "data").exists():
            return p
    return start.parents[4]

class ScopeAgent:
    """
    RFP 문서로부터 Scope Statement, RTM, WBS를 생성하는 Agent

    Pipeline:
        1. ingest: RFP 텍스트 로드
        2. extract_items: 요구사항 추출 (LLM or fallback)
        3. synthesize_wbs: WBS 구조 생성
        4. write_outputs: 파일로 저장 (JSON/CSV/MD)
        5. _save_scope_db: DB 저장 (직렬화/req_id 보정)
    """

    def __init__(self, data_dir: Optional[str] = None):
        here = Path(__file__).resolve()
        root = _find_root(here)
        self.DATA_DIR = Path(data_dir) if data_dir else (root / "data")
        self.INPUT_RFP_DIR = self.DATA_DIR / "inputs" / "RFP"
        self.OUT_DIR = self.DATA_DIR / "outputs" / "scope"
        self.INPUT_RFP_DIR.mkdir(parents=True, exist_ok=True)
        self.OUT_DIR.mkdir(parents=True, exist_ok=True)

        # DB availability flags (lazy import)
        try:
            from server.db.database import SessionLocal  # type: ignore
            from server.db import pm_models  # type: ignore
            self.SessionLocal = SessionLocal
            self.pm_models = pm_models
            self._HAS_DB = True
        except Exception as e:
            logger.warning("[ScopeAgent] DB import failed: %s", e)
            self.SessionLocal = None
            self.pm_models = None
            self._HAS_DB = False

    # -------------------------
    # Pipeline entrypoint
    # -------------------------
    async def pipeline(self, payload: Any) -> Dict[str, Any]:
        if not isinstance(payload, dict):
            try:
                payload = payload.model_dump()
            except Exception:
                try:
                    payload = payload.dict()
                except Exception:
                    payload = {}

        project_id = payload.get("project_id") or payload.get("project_name") or "default"
        documents = payload.get("documents", [])
        text = payload.get("text")
        methodology = payload.get("methodology", "waterfall")
        options = payload.get("options", {})

        # ingest
        raw_text = await self._ingest(text, documents)
        logger.info("🔵 [SCOPE] 요청: project_id=%s, methodology=%s", project_id, methodology)
        logger.info("🔵 [SCOPE] 텍스트길이: %s", len(raw_text) if raw_text else 0)

        # extract
        items = await self._extract_items(raw_text, project_id)

        # simple wbs synth
        wbs = await self._synthesize_wbs(items, depth=int(options.get("wbs_depth", 3)))

        # write outputs
        paths = await self._write_outputs(project_id, raw_text, items, wbs)

        # save to DB (if available)
        db_result = await self._save_scope_db(project_id, paths, items, wbs, payload)

        # PMP outputs placeholder (keep backward compat)
        pmp_outputs = await self._generate_pmp_outputs(project_id, paths["project_dir"], wbs, items, methodology)

        return {
            "status": "ok",
            "project_id": project_id,
            "wbs_json": str(paths["wbs_json"]),
            "rtm_csv": str(paths["rtm_csv"]),
            "scope_statement_md": str(paths["scope_md"]),
            **pmp_outputs,
            "stats": {
                "requirements": len([it for it in items if (it.get("type") or "").lower().startswith("req")]),
                "functions": len([it for it in items if (it.get("type") or "").lower().startswith("func")]),
                "deliverables": len([it for it in items if (it.get("type") or "").lower().startswith("deliv")]),
                "wbs_nodes": len(wbs.get("nodes", []))
            },
            "db": db_result
        }

    # -------------------------
    # Ingest
    # -------------------------
    async def _ingest(self, text: Optional[str], documents: List[Dict]) -> str:
        if text:
            return text
        if documents and len(documents) > 0:
            first = documents[0]
            path = first.get("path") if isinstance(first, dict) else getattr(first, "path", None)
            if path:
                p = Path(path)
                if not p.exists():
                    p = self.INPUT_RFP_DIR / path
                if p.exists():
                    # NOTE: 실제 구현에서는 docx/pdf -> text 변환 로직 필요
                    try:
                        content = p.read_text(encoding="utf-8")
                        return content
                    except Exception:
                        return f"RFP: {p.name}\n\n(문서 있음 — 텍스트 읽기 실패)"
            return "[WARN] documents provided but no readable path"
        return ""

    # -------------------------
    # Extract (LLM + fallback)
    # -------------------------
    async def _extract_items(self, raw_text: str, project_id: str) -> List[Dict[str, Any]]:
        """
        LLM을 호출하여 요구사항/기능/산출물/승인기준을 추출.
        -- 안전성 보강:
           - LLM raw 응답 타입/값을 로그로 남김
           - 다양한 SDK 반환형 처리 (str, dict, object with .content/.text/.generations 등)
           - LLM 파싱 실패 시 룰 기반 fallback
        """
        items: List[Dict[str, Any]] = []

        # fast-fail
        if not raw_text or not raw_text.strip():
            logger.warning("[SCOPE] Validation Error: No RFP text provided")
            return items

        # Build prompt (간단화)
        from .prompts import SCOPE_EXTRACT_PROMPT  # type: ignore
        prompt = SCOPE_EXTRACT_PROMPT.format(context=raw_text)

        # Try to call LLM (get_llm()는 프로젝트 내 구현에 맞게 교체)
        llm_resp = None
        try:
            llm = None
            try:
                from server.utils.llm_factory import get_llm  # type: ignore
                llm = get_llm()
            except Exception:
                llm = None

            def call_llm():
                if llm is None:
                    raise RuntimeError("LLM not available")
                # SDKs differ — try robust call
                try:
                    # support APIs expecting a single prompt string
                    if hasattr(llm, "__call__"):
                        return llm(prompt)
                    # langchain-like .generate / chat models
                    if hasattr(llm, "generate"):
                        return llm.generate([prompt])
                    # fallback
                    return llm(prompt)
                except Exception as e:
                    return e

            # run in thread
            try:
                llm_resp = await asyncio.to_thread(call_llm)
            except Exception as e:
                llm_resp = e

        except Exception as e:
            logger.warning("🟠 [SCOPE] LLM call failed: %s", e)
            llm_resp = None

        # --- PATCH: debug raw LLM response ---
        try:
            logger.debug("[SCOPE] LLM raw response type=%s", type(llm_resp))
            # repr may be huge; limit length
            try:
                raw_repr = repr(llm_resp)
                logger.debug("[SCOPE] LLM raw repr (truncated): %s", raw_repr[:1000])
            except Exception:
                logger.debug("[SCOPE] LLM raw repr not available")
        except Exception:
            pass

        # --- robust extraction of text_out from llm_resp ---
        text_out = None
        try:
            if llm_resp is None:
                text_out = None
            elif isinstance(llm_resp, str):
                text_out = llm_resp
            elif isinstance(llm_resp, dict):
                # try common keys
                for k in ("content", "text", "response", "result"):
                    if k in llm_resp and isinstance(llm_resp[k], str):
                        text_out = llm_resp[k]
                        break
                if text_out is None:
                    # dump whole dict
                    text_out = json.dumps(llm_resp, ensure_ascii=False)
            else:
                # object types: many SDKs have .content / .text / .generations / .choices
                if hasattr(llm_resp, "content"):
                    text_out = getattr(llm_resp, "content")
                elif hasattr(llm_resp, "text"):
                    text_out = getattr(llm_resp, "text")
                elif hasattr(llm_resp, "choices"):
                    ch = getattr(llm_resp, "choices")
                    # choices can be list of objects or dicts
                    try:
                        if isinstance(ch, (list,tuple)) and len(ch) > 0:
                            first = ch[0]
                            if isinstance(first, dict) and "text" in first:
                                text_out = first["text"]
                            elif hasattr(first, "text"):
                                text_out = getattr(first, "text")
                            elif hasattr(first, "message"):
                                msg = getattr(first, "message")
                                if isinstance(msg, dict) and "content" in msg:
                                    text_out = msg["content"]
                                elif hasattr(msg, "content"):
                                    text_out = getattr(msg, "content")
                    except Exception:
                        pass
                elif hasattr(llm_resp, "generations"):
                    gens = getattr(llm_resp, "generations")
                    # langchain v0.0x style: generations -> list -> Generation -> text
                    try:
                        if isinstance(gens, (list,tuple)) and len(gens) > 0:
                            g0 = gens[0]
                            if isinstance(g0, (list,tuple)) and len(g0) > 0:
                                maybe = g0[0]
                                if hasattr(maybe, "text"):
                                    text_out = getattr(maybe, "text")
                    except Exception:
                        pass

                # final fallback to str()
                if text_out is None:
                    text_out = str(llm_resp)
        except Exception as e:
            logger.exception("[SCOPE] error normalizing llm_resp: %s", e)
            text_out = None

        # If we couldn't parse LLM response text, fallback to rules
        if not text_out or not isinstance(text_out, str):
            logger.warning("🟠 [SCOPE] LLM extraction failed: %s — using fallback extraction", repr(type(llm_resp)))
            # fallback: naive sentence split (very simple)
            lines = [l.strip() for l in raw_text.splitlines() if l.strip()]
            for i, ln in enumerate(lines[:200], 1):
                typ = "requirement" if "shall" in ln.lower() or "require" in ln.lower() else "note"
                items.append({
                    "id": f"REQ-F-{i:03d}",
                    "text": ln[:1000],
                    "type": typ,
                    "category": "functional" if "shall" in ln.lower() else "other",
                    "source": "RFP"
                })
            return items

        # attempt to extract JSON block from text_out
        jmatch = re.search(r"(\{[\s\S]*\})", text_out)
        if jmatch:
            try:
                parsed = json.loads(jmatch.group(1))
                # expected structure: requirements[], functions[], deliverables[], acceptance_criteria[]
                for key in ("requirements", "functions", "deliverables", "acceptance_criteria"):
                    arr = parsed.get(key) or []
                    if isinstance(arr, list):
                        for it in arr:
                            if isinstance(it, dict):
                                items.append(it)
                            else:
                                items.append({"id": None, "text": str(it), "type": key})
            except Exception as e:
                logger.exception("[SCOPE] JSON parse from LLM output failed: %s", e)
                # fallback simple parse (split by lines)
                parts = [l.strip() for l in text_out.splitlines() if l.strip()]
                for i, ln in enumerate(parts[:200], 1):
                    items.append({"id": f"REQ-L-{i:03d}", "text": ln, "type": "inferred", "source": "LLM"})
        else:
            # no JSON found — try line-based parse of text_out
            lines = [l.strip() for l in text_out.splitlines() if l.strip()]
            for i, ln in enumerate(lines[:500], 1):
                # attempt simple extraction of req id if present
                found_id = None
                m = re.match(r"^(REQ[-_\s]?\d+)\b", ln, re.I)
                if m:
                    found_id = m.group(1).upper().replace(" ", "-")
                items.append({
                    "id": found_id or None,
                    "text": ln,
                    "type": "requirement" if "require" in ln.lower() or "shall" in ln.lower() else "note",
                    "source": "LLM"
                })

        # normalize ids: ensure id field exists with pattern REQ-###
        normalized = []
        next_seq = 1
        for it in items:
            rid = it.get("id") or it.get("req_id") or None
            if rid is None:
                rid = f"REQ-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{next_seq:03d}"
                next_seq += 1
            else:
                # normalize forms like 'R1' -> REQ-001 if numeric
                if isinstance(rid, str):
                    rr = re.search(r"\d+", rid)
                    if rr:
                        num = int(rr.group(0))
                        rid = f"REQ-{num:03d}"
            it["req_id"] = rid
            # ensure title/description trimmed
            it["title"] = (it.get("title") or (it.get("text") or "") )[:1000]
            it["description"] = it.get("description") or it.get("text") or ""
            it.setdefault("type", "functional" if "shall" in it.get("text","").lower() else "other")
            normalized.append(it)
        return normalized

    # -------------------------
    # WBS synth (simple)
    # -------------------------
    async def _synthesize_wbs(self, items: List[Dict[str, Any]], depth: int = 3) -> Dict[str, Any]:
        nodes = [{
            "id": "WBS-1",
            "name": "Project",
            "level": 1,
            "children": []
        }]
        # make a few phases
        phases = []
        for i in range(1, 4):
            phases.append({"id": f"WBS-1.{i}", "name": f"Phase {i}", "level": 2, "children": []})
        nodes[0]["children"] = phases
        # attach few tasks under first phase
        for j in range(1, 4):
            phases[0]["children"].append({
                "id": f"WBS-1.1.{j}",
                "name": f"Task {j}",
                "level": 3,
                "children": []
            })
        return {"nodes": nodes, "depth": depth}

    # -------------------------
    # Write outputs (files)
    # -------------------------
    async def _write_outputs(self, project_id: Any, raw: str, items: List[Dict[str, Any]], wbs: Dict[str, Any]) -> Dict[str, Path]:
        proj_dir = self.OUT_DIR / str(project_id)
        proj_dir.mkdir(parents=True, exist_ok=True)

        # WBS JSON
        wbs_json = proj_dir / "wbs_structure.json"
        wbs_json.write_text(json.dumps(wbs, ensure_ascii=False, indent=2), encoding="utf-8")

        # RTM CSV
        rtm_csv = proj_dir / "rtm.csv"
        with open(rtm_csv, "w", encoding="utf-8", newline="") as f:
            f.write("req_id,title,description,source\n")
            for it in items:
                req_id = it.get("req_id") or it.get("id") or ""
                title = (it.get("title") or it.get("text") or "").replace("\n", " ").replace(",", ";")
                desc = (it.get("description") or "").replace("\n", " ").replace(",", ";")
                src = it.get("source") or ""
                f.write(f"{req_id},{title},{desc},{src}\n")

        # Scope statement MD
        scope_md = proj_dir / "scope_statement.md"
        scope_md.write_text("# Scope Statement\n\n" + (raw or "") + "\n", encoding="utf-8")

        return {
            "project_dir": proj_dir,
            "wbs_json": wbs_json,
            "rtm_csv": rtm_csv,
            "scope_md": scope_md
        }

    # -------------------------
    # DB Save (safe)
    # -------------------------
    async def _save_scope_db(self, project_id: Any, paths: Dict[str, Path], items: List[Dict[str,Any]], wbs: Dict[str,Any], payload: Dict[str,Any]) -> Dict[str,Any]:
        """
        안전하게 DB에 저장:
          - dict/list -> json.dumps 직렬화
          - 요구사항 저장 시 req_id가 없으면 자동 생성(로그 기록)
          - 실패시 예외를 로깅하고 실패정보 리턴
        """
        result = {"saved_requirements": 0, "saved_scope_row": False, "errors": []}
        if not self._HAS_DB:
            logger.info("[SCOPE] DB not available; skip DB persistence")
            return result

        db = None
        try:
            db = self.SessionLocal()
            # 1) save requirements
            saved = 0
            for idx, r in enumerate(items, start=1):
                req_id = r.get("req_id") or r.get("id")
                if not req_id:
                    # 자동생성 (안전장치)
                    req_id = f"REQ-AUTO-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{idx:03d}"
                    logger.info("[SCOPE] generated req_id=%s for item title=%s", req_id, (r.get("title") or "")[:80])
                try:
                    rr = self.pm_models.PM_Requirement(
                        project_id=project_id,
                        req_id=str(req_id),
                        title=(r.get("title") or "")[:1000],
                        description=(r.get("description") or "")[:4000],
                        source_doc=str(paths.get("rtm_csv")),
                        priority=(r.get("priority") or "Medium"),
                        status=(r.get("status") or "Candidate"),
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow(),
                        type=(r.get("type") or "functional")
                    )
                    db.add(rr)
                    saved += 1
                except Exception as e:
                    logger.exception("[SCOPE] Failed to add requirement %s: %s", req_id, e)
                    result["errors"].append({"index": idx, "req_id": req_id, "error": repr(e)})

            try:
                db.commit()
                result["saved_requirements"] = saved
            except Exception as e:
                db.rollback()
                logger.exception("[SCOPE] commit failed when saving requirements: %s", e)
                result["errors"].append({"phase":"commit_requirements","error":repr(e)})

            # 2) save scope summary row (pm_scope)
            try:
                full_json = {
                    "status": "ok",
                    "project_id": project_id,
                    "wbs_json_path": str(paths.get("wbs_json")),
                    "rtm_csv": str(paths.get("rtm_csv"))
                }
                # ensure json string (avoid dict binding error)
                full_json_str = json.dumps(full_json, ensure_ascii=False)
                row = self.pm_models.PM_Scope(
                    project_id=project_id,
                    scope_statement_md=str(paths.get("scope_md")),
                    rtm_csv=str(paths.get("rtm_csv")),
                    wbs_json=str(paths.get("wbs_json")),
                    wbs_excel=None,
                    rtm_excel=None,
                    scope_statement_excel=None,
                    project_charter_docx=None,
                    tailoring_excel=None,
                    full_json=full_json_str,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                db.add(row)
                db.commit()
                result["saved_scope_row"] = True
            except Exception as e:
                db.rollback()
                logger.exception("[SCOPE] pm_scope insert failed: %s", e)
                result["errors"].append({"phase":"save_scope_row","error":repr(e)})

        except Exception as e:
            logger.exception("[SCOPE] DB save failed: %s", e)
            result["errors"].append({"phase":"outer","error":repr(e)})
        finally:
            try:
                if db is not None:
                    db.close()
            except Exception:
                pass
        return result

    # -------------------------
    # PMP outputs (placeholder)
    # -------------------------
    async def _generate_pmp_outputs(self, project_id: str, project_dir: Path, wbs: Dict, requirements: List[Dict], methodology: str) -> Dict[str,str]:
        # minimal placeholder to avoid crashing callers
        return {
            "wbs_excel": None,
            "rtm_excel": None,
            "scope_statement_excel": None,
            "project_charter_docx": None,
            "tailoring_excel": None
        }
