# server/workflow/agents/scope_agent/pipeline.py
# ScopeAgent: RFP -> Requirements, SRS, RTM 초기화, PMP 산출물 생성
import json
import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
import logging
import csv
import copy
import re

logger = logging.getLogger("scope.agent")

# LLM factory (optional)
try:
    from server.utils.config import get_llm
    _HAS_LLM_FACTORY = True
except Exception:
    get_llm = None
    _HAS_LLM_FACTORY = False

# doc reader utilities (ingest)
try:
    from server.utils.doc_reader import ingest_text, DocReadError
except Exception:
    # fallback simple ingest
    async def ingest_text(text_input, documents, search_paths):
        # If text_input provided, return it
        if text_input:
            return (text_input, None)
        # try first document path if present
        if documents and len(documents) > 0:
            p = documents[0]
            if isinstance(p, str):
                fp = Path(p)
            elif isinstance(p, dict):
                fp = Path(p.get("path", ""))
            else:
                fp = getattr(p, "path", None)
                if fp:
                    fp = Path(fp)
            try:
                txt = fp.read_text(encoding="utf-8")
                return (txt, str(fp))
            except Exception:
                return ("", None)
        return ("", None)

# DB models
try:
    from server.db.database import SessionLocal
    from server.db import pm_models
    _HAS_DB = True
except Exception as e:
    logger.warning("[ScopeAgent] DB import failed: %s", e)
    SessionLocal = None
    pm_models = None
    _HAS_DB = False

# prompts import (use SCOPE_EXTRACT_PROMPT)
try:
    from .prompts import SCOPE_EXTRACT_PROMPT, RTM_PROMPT, WBS_SYNTHESIS_PROMPT
except Exception:
    SCOPE_EXTRACT_PROMPT = """
당신은 PMP 표준을 준수하는 PMO 분석가입니다.
아래 문서에서 요구사항, 관련 기능, 산출물, 승인기준을 구조화하여 추출하세요.
출력 JSON:
{
  "requirements":[{"req_id":"REQ-001","title":"...","type":"functional","priority":"High","description":"...","source_span":"..."}],
  "functions": [],
  "deliverables": [],
  "acceptance_criteria": []
}
문서:
{context}
"""
    RTM_PROMPT = "RTM mapping for requirements: {requirements}"
    WBS_SYNTHESIS_PROMPT = "WBS synthesis for items: {items}"


def _find_root(start: Path) -> Path:
    for p in start.parents:
        if (p / "data").exists():
            return p
    return start.parents[4] if len(start.parents) >= 5 else start.parent


class ScopeAgent:
    """Scope Management Agent (RFP -> Requirements/SRS/RTM/WBS draft)"""

    def __init__(self, data_dir: Optional[str] = None):
        here = Path(__file__).resolve()
        root = _find_root(here)
        self.DATA_DIR = Path(data_dir) if data_dir else (root / "data")
        self.INPUT_RFP_DIR = self.DATA_DIR / "inputs" / "RFP"
        self.OUT_DIR = self.DATA_DIR / "outputs" / "scope"
        self.INPUT_RFP_DIR.mkdir(parents=True, exist_ok=True)
        self.OUT_DIR.mkdir(parents=True, exist_ok=True)

    async def pipeline(self, payload: Any) -> Dict[str, Any]:
        if not isinstance(payload, dict):
            if hasattr(payload, "model_dump"):
                payload = payload.model_dump()
            elif hasattr(payload, "dict"):
                payload = payload.dict()
            else:
                payload = {}

        project_id = payload.get("project_id") or payload.get("project_name") or "default"
        documents = payload.get("documents", [])
        text_input = payload.get("text")
        methodology = (payload.get("methodology") or "waterfall").lower()

        # ensure project dir
        proj_dir = self.OUT_DIR / str(project_id)
        proj_dir.mkdir(parents=True, exist_ok=True)

        # ingest
        raw_text, rfp_path = await asyncio.to_thread(
            ingest_text,
            text_input,
            documents,
            [self.INPUT_RFP_DIR, self.DATA_DIR / "inputs" / "RFP", self.DATA_DIR]
        )
        if not raw_text or not str(raw_text).strip():
            logger.warning("[SCOPE] No RFP text provided")
            return {"status": "error", "message": "No RFP text provided", "project_id": project_id}

        logger.info(f"🔵 [SCOPE] 요청: project_id={project_id}, methodology={methodology}")
        logger.info(f"🔵 [SCOPE] 텍스트길이: {len(raw_text)}")

        # extract items
        items = await self._extract_items(raw_text, project_id)

        # save requirements to DB
        if _HAS_DB and pm_models is not None and items.get("requirements"):
            try:
                await asyncio.to_thread(self._save_requirements_db, project_id, items["requirements"])
            except Exception as e:
                logger.exception("[SCOPE] save_requirements_db failed: %s", e)

        # generate SRS
        srs_path = proj_dir / "SRS.md"
        try:
            await asyncio.to_thread(self._generate_srs, project_id, items, srs_path)
            logger.info(f"[SCOPE] Generated SRS: {srs_path}")
        except Exception as e:
            logger.exception("[SCOPE] SRS generation failed: %s", e)
            srs_path = None

        # initialize RTM
        rtm_csv_path = proj_dir / "rtm_initial.csv"
        try:
            rtm_json = await self._initialize_rtm(items, rtm_csv_path, project_id)
            logger.info(f"[SCOPE] Initialized RTM: {rtm_csv_path}")
        except Exception as e:
            logger.exception("[SCOPE] RTM initialization failed: %s", e)
            rtm_json = {"mappings": []}

        # project docs
        charter_path = proj_dir / "project_charter.md"
        business_plan_path = proj_dir / "business_plan.md"
        try:
            await asyncio.to_thread(self._generate_project_documents, project_id, items, charter_path, business_plan_path)
        except Exception as e:
            logger.exception("[SCOPE] project doc generation failed: %s", e)

        # write requirements json
        requirements_json_path = proj_dir / "requirements.json"
        requirements_json_path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")

        # generate PMP outputs (may be slow)
        pmp_outputs = {}
        try:
            pmp_outputs = await asyncio.to_thread(self._generate_pmp_outputs, project_id, proj_dir, items)
        except Exception as e:
            logger.exception("[SCOPE] PMP outputs generation failed: %s", e)

        scope_out = {
            "status": "ok",
            "project_id": project_id,
            "requirements_json": str(requirements_json_path),
            "requirements": items.get("requirements", []),
            "functions": items.get("functions", []),
            "deliverables": items.get("deliverables", []),
            "acceptance_criteria": items.get("acceptance_criteria", []),
            "rtm_json": rtm_json,
            "rtm_csv": str(rtm_csv_path) if rtm_csv_path.exists() else None,
            "srs_path": str(srs_path) if srs_path and Path(srs_path).exists() else None,
            "charter_path": str(charter_path) if charter_path.exists() else None,
            "business_plan_path": str(business_plan_path) if business_plan_path.exists() else None,
            "pmp_outputs": {k: v for k, v in pmp_outputs.items() if v is not None},
            "stats": {
                "requirements": len(items.get("requirements", [])),
                "functions": len(items.get("functions", [])),
                "deliverables": len(items.get("deliverables", [])),
                "acceptance_criteria": len(items.get("acceptance_criteria", []))
            },
            "message": "Requirements extracted. Pass to Schedule Agent for WBS generation."
        }
        logger.info(f"[SCOPE] 파이프라인 완료: project_id={project_id}")
        return scope_out

    # -------------------------
    # Instance helper methods
    # -------------------------
    async def _extract_items(self, text: str, project_id: Any) -> Dict[str, Any]:
        """Extract requirements/functions/deliverables using LLM (if available) or fallback rules"""
        logger.info("🟡 [SCOPE] _extract_items() 시작")
        # get llm
        llm = None
        try:
            if _HAS_LLM_FACTORY and get_llm is not None:
                llm = get_llm()
                logger.info("🟡 [SCOPE] LLM factory provided an LLM instance")
        except Exception as e:
            logger.warning("LLM factory failed: %s", e)
            llm = None

        def call_llm_sync(prompt_text: str):
            if not llm:
                raise RuntimeError("No LLM available")
            # some LLM SDKs accept dict/messages — we assume simple text prompt here
            if hasattr(llm, "generate"):
                return llm.generate([{"role":"user","content": prompt_text}])
            else:
                return llm(prompt_text)

        prompt = SCOPE_EXTRACT_PROMPT.replace("{context}", text[:8000]) if "{context}" in SCOPE_EXTRACT_PROMPT else SCOPE_EXTRACT_PROMPT.format(context=text[:8000])

        # call
        resp = None
        try:
            if llm:
                logger.info("🟡 [SCOPE] LLM 호출 시도")
                resp = await asyncio.to_thread(call_llm_sync, prompt)
            else:
                raise RuntimeError("LLM absent - using fallback")
        except Exception as e:
            logger.warning(f"🟠 [SCOPE] LLM extraction failed: {e} — using fallback extraction")
            # fallback: rule-based
            return self._fallback_extract(text)

        # parse response robustly
        try:
            # resp may be string, object with .content/.text, or langchain-style
            if isinstance(resp, str):
                text_out = resp
            elif hasattr(resp, "content"):
                text_out = resp.content
            elif hasattr(resp, "text"):
                t = resp.text
                text_out = t() if callable(t) else t
            elif hasattr(resp, "generations"):
                # langchain-like
                gens = resp.generations
                # try to find text
                if isinstance(gens, list) and gens and isinstance(gens[0], list):
                    text_out = gens[0][0].text
                else:
                    text_out = str(resp)
            else:
                text_out = str(resp)

            if not isinstance(text_out, (str, bytes)):
                text_out = str(text_out)

            # try to extract JSON block
            m = re.search(r"(\{.*\})", text_out, re.S)
            if m:
                jtxt = m.group(1)
                data = json.loads(jtxt)
            else:
                # try to parse entire text as json
                try:
                    data = json.loads(text_out)
                except Exception:
                    logger.warning("[SCOPE] JSON block not found in LLM output, using fallback parser")
                    return self._fallback_extract(text)
            # normalize keys
            out = {
                "requirements": data.get("requirements", []),
                "functions": data.get("functions", []),
                "deliverables": data.get("deliverables", []),
                "acceptance_criteria": data.get("acceptance_criteria", [])
            }
            # ensure req_id assigned
            for idx, r in enumerate(out["requirements"], start=1):
                if not r.get("req_id"):
                    r["req_id"] = r.get("req_id") or f"REQ-{idx:03d}"
            logger.info(f"[SCOPE] 추출 완료: requirements={len(out['requirements'])}")
            return out

        except Exception as e:
            logger.exception("[SCOPE] 응답 파싱 실패: %s", e)
            return self._fallback_extract(text)

    def _fallback_extract(self, raw_text: str) -> Dict[str, List[Dict[str, Any]]]:
        """Naive keyword-based extraction (fallback)"""
        reqs = []
        funcs = []
        dels = []
        acc = []
        idx = 1
        for para in [p.strip() for p in raw_text.split("\n\n") if p.strip()]:
            low = para.lower()
            if any(k in low for k in ("require", "요구", "must", "shall")):
                reqs.append({
                    "req_id": f"REQ-{idx:03d}",
                    "title": para[:80],
                    "type": "functional" if any(w in low for w in ("function", "feature", "기능")) else "non-functional",
                    "priority": "Medium",
                    "description": para,
                    "source_span": "RFP"
                })
                idx += 1
            elif any(k in low for k in ("feature", "function", "기능")):
                funcs.append({"id": f"FUNC-{idx:03d}", "title": para[:80], "description": para}); idx += 1
            elif any(k in low for k in ("deliverable", "산출물")):
                dels.append({"id": f"DEL-{idx:03d}", "title": para[:80], "description": para}); idx += 1
            elif any(k in low for k in ("acceptance", "승인", "criteria", "검증")):
                acc.append({"id": f"ACC-{idx:03d}", "title": para[:80], "description": para}); idx += 1
        return {"requirements": reqs, "functions": funcs, "deliverables": dels, "acceptance_criteria": acc}

    def _save_requirements_db(self, project_id: Any, requirements: List[Dict[str, Any]]):
        """Insert or update PM_Requirement rows"""
        if not _HAS_DB or pm_models is None:
            logger.info("[SCOPE] DB not available; skipping requirement save")
            return
        db = SessionLocal()
        try:
            for r in requirements:
                req_id = r.get("req_id") or r.get("id")
                if not req_id:
                    logger.warning("[SCOPE] skipping requirement without req_id")
                    continue
                existing = db.query(pm_models.PM_Requirement).filter(
                    pm_models.PM_Requirement.req_id == req_id,
                    pm_models.PM_Requirement.project_id == str(project_id)
                ).one_or_none()
                if existing:
                    existing.title = r.get("title") or existing.title
                    existing.type = r.get("type") or existing.type
                    existing.priority = r.get("priority") or existing.priority
                    existing.description = r.get("description") or existing.description
                    existing.source_doc = r.get("source_span") or existing.source_doc
                    existing.updated_at = datetime.utcnow()
                else:
                    rec = pm_models.PM_Requirement(
                        project_id=str(project_id),
                        req_id=req_id,
                        title=r.get("title") or "",
                        type=r.get("type") or "functional",
                        priority=r.get("priority") or "Medium",
                        description=r.get("description") or "",
                        source_doc=r.get("source_span"),
                        status="Open",
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow()
                    )
                    db.add(rec)
            db.commit()
        except Exception as e:
            logger.exception("[SCOPE] Saving requirements failed: %s", e)
            db.rollback()
        finally:
            db.close()

    async def _initialize_rtm(self, items: Dict[str, Any], csv_path: Path, project_id: Any) -> Dict[str, Any]:
        """Initialize RTM with requirements only"""
        mappings = []
        reqs = items.get("requirements", [])
        for r in reqs:
            mappings.append({
                "req_id": r.get("req_id"),
                "title": r.get("title"),
                "type": r.get("type"),
                "priority": r.get("priority"),
                "wbs_id": "",
                "test_case": "",
                "verification_status": "Pending WBS"
            })
        # write CSV
        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "req_id", "title", "type", "priority", "wbs_id", "test_case", "verification_status"
            ])
            writer.writeheader()
            for m in mappings:
                writer.writerow(m)
        # DB save (skip entries without req_id)
        if _HAS_DB and pm_models is not None:
            db = SessionLocal()
            try:
                db.query(pm_models.PM_RTM).filter(pm_models.PM_RTM.project_id == str(project_id)).delete()
                for m in mappings:
                    req_id = m.get("req_id")
                    if not req_id:
                        logger.warning(f"[SCOPE] Skipping RTM entry with empty req_id: {m}")
                        continue
                    rec = pm_models.PM_RTM(
                        project_id=str(project_id),
                        req_id=req_id,
                        wbs_id=m.get("wbs_id") or None,
                        test_case=m.get("test_case") or None,
                        verification_status=m.get("verification_status") or "Candidate",
                        created_at=datetime.utcnow()
                    )
                    db.add(rec)
                db.commit()
            except Exception as e:
                logger.exception("[SCOPE] Saving RTM to DB failed: %s", e)
                db.rollback()
            finally:
                db.close()
        return {"mappings": mappings}

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

    def _generate_project_documents(self, project_id: Any, items: Dict[str, Any], charter_path: Path, business_path: Path):
        charter_path.parent.mkdir(parents=True, exist_ok=True)
        with open(charter_path, "w", encoding="utf-8") as f:
            f.write(f"# Project Charter\n**Project ID:** {project_id}\n**Date:** {datetime.utcnow().date().isoformat()}\n\n")
        with open(business_path, "w", encoding="utf-8") as f:
            f.write(f"# Business Plan\n**Project ID:** {project_id}\n**Date:** {datetime.utcnow().date().isoformat()}\n\n")
        return str(charter_path), str(business_path)

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
