# server/workflow/agents/scope_agent/pipeline.py (DOCX 지원 추가)
import json
import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
import logging
import csv
import copy
import re
from server.utils.doc_reader import read_texts, ingest_text, DocReadError


logger = logging.getLogger("scope.agent")

# LLM import
try:
    from server.utils.config import get_llm
    _HAS_LLM = True
except Exception:
    get_llm = None
    _HAS_LLM = False

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

# ✅ 프롬프트 import (fallback 포함)
try:
    from .prompts import SCOPE_EXTRACT_PROMPT, RTM_PROMPT
except Exception:
    # Fallback 프롬프트
    SCOPE_EXTRACT_PROMPT = """
당신은 PMP 표준을 준수하는 PMO 분석가입니다.
아래 문서에서 요구사항, 기능, 산출물, 승인기준을 추출하세요.

출력 JSON:
{{
  "requirements": [{{"req_id":"REQ-001","title":"...","type":"functional","priority":"High","description":"...","source_span":"..."}}],
  "functions": [...],
  "deliverables": [...],
  "acceptance_criteria": [...]
}}

문서:
{context}
"""
    RTM_PROMPT = "RTM mapping for requirements: {requirements}"


def _find_root(start: Path) -> Path:
    for p in start.parents:
        if (p / "data").exists():
            return p
    return start.parents[4] if len(start.parents) >= 5 else start.parent


class ScopeAgent:
    """Scope Management Agent (PMP 5.0)
    
    Supports RFP document formats: PDF, TXT, MD, DOCX
    """
    
    def __init__(self, data_dir: Optional[str] = None):
        here = Path(__file__).resolve()
        root = _find_root(here)
        self.DATA_DIR = Path(data_dir) if data_dir else (root / "data")
        self.INPUT_RFP_DIR = self.DATA_DIR / "inputs" / "RFP"
        self.OUT_DIR = self.DATA_DIR / "outputs" / "scope"
        self.INPUT_RFP_DIR.mkdir(parents=True, exist_ok=True)
        self.OUT_DIR.mkdir(parents=True, exist_ok=True)

    async def pipeline(self, payload: Any) -> Dict[str, Any]:
        """Scope Agent 파이프라인
        
        RFP 문서 형식 지원: PDF, TXT, MD, DOCX
        """
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

        # Ensure output project dir
        proj_dir = self.OUT_DIR / str(project_id)
        proj_dir.mkdir(parents=True, exist_ok=True)

        # 1) Ingest RFP - ✅ 공통 유틸 사용 (PDF, TXT, MD, DOCX 지원)
        raw_text, rfp_path = await asyncio.to_thread(
            ingest_text,
            text_input,
            documents,
            [self.INPUT_RFP_DIR, self.DATA_DIR / "inputs" / "RFP", self.DATA_DIR]
        )
        if not raw_text.strip():
            return {"status": "error", "message": "No RFP text provided", "project_id": project_id}

        # 2) Extract items (LLM or fallback)
        logger.info(f"[SCOPE] Extracting requirements for project {project_id}")
        items = await self._extract_items(raw_text, project_id)

        # 3) Save requirements to DB (존재 시 upsert)
        if _HAS_DB and pm_models is not None and items.get("requirements"):
            try:
                await asyncio.to_thread(self._save_requirements_db, project_id, items["requirements"])
            except Exception as e:
                logger.exception("save_requirements_db failed: %s", e)

        # 4) Generate SRS
        srs_path = proj_dir / "SRS.md"
        try:
            await asyncio.to_thread(self._generate_srs, project_id, items, srs_path)
            logger.info(f"[SCOPE] Generated SRS: {srs_path}")
        except Exception as e:
            logger.exception("SRS generation failed: %s", e)
            srs_path = None

        # 5) Initialize RTM (requirements only, WBS will be done by Schedule Agent)
        rtm_json = {"mappings": []}
        rtm_csv_path = proj_dir / "rtm_initial.csv"
        try:
            rtm_json = await self._initialize_rtm(items, rtm_csv_path, project_id)
            logger.info(f"[SCOPE] Initialized RTM: {rtm_csv_path}")
        except Exception as e:
            logger.exception("RTM initialization failed: %s", e)

        # 6) Generate project documents
        charter_path = proj_dir / "project_charter.md"
        business_plan_path = proj_dir / "business_plan.md"
        try:
            await asyncio.to_thread(
                self._generate_project_documents, 
                project_id, 
                items, 
                charter_path, 
                business_plan_path
            )
        except Exception as e:
            logger.exception("project doc generation failed: %s", e)

        # 7) Write requirements JSON
        requirements_json_path = proj_dir / "requirements.json"
        requirements_json_path.write_text(
            json.dumps(items, ensure_ascii=False, indent=2), 
            encoding="utf-8"
        )

        # 8) Generate PMP outputs
        pmp_outputs = {}
        try:
            pmp_outputs = await asyncio.to_thread(
                self._generate_pmp_outputs, 
                project_id, 
                proj_dir, 
                items
            )
        except Exception as e:
            logger.exception("PMP outputs generation failed: %s", e)

        # ✅ None 값 필터링 (Pydantic validation 통과용)
        pmp_outputs_filtered = {k: v for k, v in pmp_outputs.items() if v is not None}

        # Final output
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
            "pmp_outputs": pmp_outputs_filtered,
            "stats": {
                "requirements": len(items.get("requirements", [])),
                "functions": len(items.get("functions", [])),
                "deliverables": len(items.get("deliverables", [])),
                "acceptance_criteria": len(items.get("acceptance_criteria", []))
            },
            "message": "Requirements extracted. Pass to Schedule Agent for WBS generation."
        }

        return scope_out

    # -------------------------
    # Helper methods
    # -------------------------

    async def _extract_items(
        self, 
        raw_text: str, 
        project_id: Any
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Extract structured requirements"""
        if _HAS_LLM and get_llm is not None and raw_text and raw_text.strip():
            prompt = SCOPE_EXTRACT_PROMPT.format(context=raw_text)
            try:
                llm = get_llm()
                def call_llm():
                    return llm.generate(prompt) if hasattr(llm, "generate") else llm(prompt)
                
                resp = await asyncio.to_thread(call_llm)
                text_out = resp if isinstance(resp, str) else getattr(resp, "text", str(resp))
                
                # Extract JSON
                m = re.search(r"(\{.*\})", text_out, re.S)
                jtxt = m.group(1) if m else text_out
                data = json.loads(jtxt)
                
                # Ensure all keys
                for k in ("requirements", "functions", "deliverables", "acceptance_criteria"):
                    if k not in data:
                        data[k] = []
                return data
                
            except Exception as e:
                logger.exception("LLM extraction failed: %s — falling back", e)
        
        # Fallback
        return self._fallback_extract(raw_text)

    def _fallback_extract(self, raw_text: str) -> Dict[str, List[Dict[str, Any]]]:
        """Naive keyword-based extraction"""
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
                funcs.append({
                    "id": f"FUNC-{idx:03d}",
                    "title": para[:80],
                    "description": para
                })
                idx += 1
                
            elif any(k in low for k in ("deliverable", "산출물")):
                dels.append({
                    "id": f"DEL-{idx:03d}",
                    "title": para[:80],
                    "description": para
                })
                idx += 1
                
            elif any(k in low for k in ("acceptance", "승인", "criteria", "검증")):
                acc.append({
                    "id": f"ACC-{idx:03d}",
                    "title": para[:80],
                    "description": para
                })
                idx += 1
                
        return {
            "requirements": reqs,
            "functions": funcs,
            "deliverables": dels,
            "acceptance_criteria": acc
        }

    def _save_requirements_db(
        self, 
        project_id: Any, 
        requirements: List[Dict[str, Any]]
    ):
        """Insert or update PM_Requirement rows"""
        if not _HAS_DB or pm_models is None:
            logger.info("DB not available; skipping requirement save")
            return
            
        db = SessionLocal()
        try:
            for r in requirements:
                req_id = r.get("req_id") or r.get("id")
                if not req_id:
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
            logger.exception("Saving requirements failed: %s", e)
            db.rollback()
        finally:
            db.close()

    async def _initialize_rtm(
        self, 
        items: Dict[str, Any], 
        csv_path: Path, 
        project_id: Any
    ) -> Dict[str, Any]:
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
        
        # Write CSV
        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "req_id", "title", "type", "priority", 
                "wbs_id", "test_case", "verification_status"
            ])
            writer.writeheader()
            for m in mappings:
                writer.writerow(m)
        
        # ✅ DB 저장시 req_id가 None인 경우 스킵
        if _HAS_DB and pm_models is not None:
            db = SessionLocal()
            try:
                # Delete existing
                db.query(pm_models.PM_RTM).filter(
                    pm_models.PM_RTM.project_id == str(project_id)
                ).delete()
                
                for m in mappings:
                    req_id = m.get("req_id")
                    # ✅ req_id가 None이거나 빈 문자열이면 스킵
                    if not req_id or req_id == "":
                        logger.warning(f"Skipping RTM entry with empty req_id: {m}")
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
                logger.exception("Saving RTM to DB failed: %s", e)
                db.rollback()
            finally:
                db.close()
        
        return {"mappings": mappings}

    def _generate_srs(
        self, 
        project_id: Any, 
        items: Dict[str, Any], 
        out_path: Path
    ):
        """Generate SRS"""
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
            
            f.write("## 2. Functions\n\n")
            for fn in items.get("functions", []):
                f.write(f"- **{fn.get('id')}:** {fn.get('title')}\n")
            
            f.write("\n## 3. Deliverables\n\n")
            for d in items.get("deliverables", []):
                f.write(f"- **{d.get('id')}:** {d.get('title')}\n")
            
            f.write("\n## 4. Acceptance Criteria\n\n")
            for a in items.get("acceptance_criteria", []):
                f.write(f"- **{a.get('id')}:** {a.get('title')}\n")
        
        return str(out_path)

    def _generate_project_documents(
        self, 
        project_id: Any, 
        items: Dict[str, Any], 
        charter_path: Path, 
        business_path: Path
    ):
        """Generate project charter and business plan"""
        charter_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(charter_path, "w", encoding="utf-8") as f:
            f.write(f"# Project Charter\n")
            f.write(f"**Project ID:** {project_id}\n")
            f.write(f"**Date:** {datetime.utcnow().date().isoformat()}\n\n")
            f.write("## Project Purpose\n\n")
            f.write("## Objectives\n\n")
            f.write("## Success Criteria\n\n")
        
        with open(business_path, "w", encoding="utf-8") as f:
            f.write(f"# Business Plan\n")
            f.write(f"**Project ID:** {project_id}\n")
            f.write(f"**Date:** {datetime.utcnow().date().isoformat()}\n\n")
            f.write("## Business Case\n\n")
            f.write("## ROI Analysis\n\n")
        
        return str(charter_path), str(business_path)

    def _generate_pmp_outputs(
        self, 
        project_id: Any, 
        project_dir: Path, 
        requirements: Dict[str, Any]
    ) -> Dict[str, Optional[str]]:
        """Generate PMP standard outputs"""
        outputs = {}
        
        try:
            from .outputs.scope_statement import ScopeStatementGenerator
            scp = project_dir / f"{project_id}_ScopeStatement.xlsx"
            outputs["scope_statement_excel"] = ScopeStatementGenerator.generate(
                project_id, requirements, scp
            )
        except Exception as e:
            outputs["scope_statement_excel"] = None
            logger.debug("ScopeStatementGenerator not available: %s", e)
        
        return outputs