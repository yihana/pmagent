# server/workflow/pm_analyzer.py
from __future__ import annotations
import json, re
from typing import List, Dict, Any, Optional
from datetime import date
from server.workflow.agents.agent import Agent  # 기존 베이스 유지
from typing import List, Dict
from server.utils.config import settings  # 기존 AOAI 설정
from server.utils.config import get_llm

ACTION_ITEM_SCHEMA = {
    "type": "array",
    "items": {
        "type":"object",
        "properties":{
            "assignee":{"type":["string","null"]},
            "task":{"type":"string"},
            "due_date":{"type":["string","null"]},      # YYYY-MM-DD
            "priority":{"type":"string"},               # Low|Medium|High
            "status":{"type":"string"},                 # Open|Doing|Done
            "module":{"type":["string","null"]},        # FI|SD|MM|PP|EWM
            "phase":{"type":["string","null"]},         # 요구|설계|개발|테스트|인수
            "evidence_span":{"type":["string","null"]},
            "expected_effort":{"type":["number","null"]},
            "expected_value":{"type":["number","null"]}
        },
        "required":["task"]
    }
}

SYSTEM_PROMPT = """You are a PM Analyzer for ERP projects (SAP).
Extract action items and map to ERP module (FI/SD/MM/PP/EWM...) and project phase (요구/설계/개발/테스트/인수).
Include evidence_span: exact text snippet from the source.
If hints exist, fill expected_effort (hours or MD) and expected_value (benefit in 만원).
Return pure JSON only that matches the provided schema.
"""

def _schema_hint() -> str:
    return json.dumps(ACTION_ITEM_SCHEMA, ensure_ascii=False)

def _build_prompt(doc_type: str, text: str, project_meta: Optional[dict]) -> str:
    head = f"DocumentType: {doc_type}\nText:\n{text[:8000]}"
    meta = f"\n\nProjectMeta:\n{json.dumps(project_meta, ensure_ascii=False)}" if project_meta else ""
    schema = "\n\nJSON Schema:\n" + _schema_hint()
    return head + meta + schema

class PM_AnalyzerAgent(Agent):
    """기존 agent.py 시그니처(run) 그대로 사용."""

    def analyze_minutes(self, minutes_text: str, project_meta: Optional[dict]=None):
        return self._call_llm("meeting", minutes_text, project_meta)

    def analyze_rfp(self, rfp_text: str, project_meta: Optional[dict]=None):
        return self._call_llm("rfp", rfp_text, project_meta)

    def analyze_proposal(self, proposal_text: str, project_meta: Optional[dict]=None):
        return self._call_llm("proposal", proposal_text, project_meta)

    def analyze_issue(self, issue_text: str, project_meta: Optional[dict]=None):
        return self._call_llm("issue", issue_text, project_meta)

    # 공통 LLM 호출
    def _call_llm(self, doc_type: str, text: str, project_meta: Optional[dict]) -> List[Dict[str, Any]]:
        prompt = _build_prompt(doc_type, text, project_meta)
        try:
            out = self.run(system=SYSTEM_PROMPT, prompt=prompt, context=None)  # 패턴 A
        except TypeError:
            out = self.run(prompt, system=SYSTEM_PROMPT, tools=None, context=None)  # 패턴 B

        items = _parse_items(out, text)
        return items

def _parse_items(raw: str, original: str) -> List[Dict[str, Any]]:
    cleaned = re.sub(r"```(?:json)?|```", "", raw).strip()
    try:
        arr = json.loads(cleaned)
        if isinstance(arr, list):
            return [_normalize(i, original) for i in arr][:200]
        if isinstance(arr, dict) and isinstance(arr.get("items"), list):
            return [_normalize(i, original) for i in arr["items"]][:200]
    except Exception:
        pass
    # fallback 규칙
    return _fallback(original)

def _normalize(d: Dict[str, Any], original: str) -> Dict[str, Any]:
    task = (d.get("task") or "").strip() or (original.splitlines()[0][:60] if original else "TBD")
    pr = (d.get("priority") or "Medium").capitalize()
    if pr not in ["Low", "Medium", "High"]:
        pr = "Medium"
    status = (d.get("status") or "Open").capitalize()
    module = d.get("module")
    phase = d.get("phase")
    if not module:
        m = re.search(r"\b(FI|SD|MM|PP|EWM)\b", task, re.I)
        module = m.group(1).upper() if m else None
    if not phase:
        p = re.search(r"(요구|설계|개발|테스트|인수)", task)
        phase = p.group(1) if p else None
    return {
        "assignee": d.get("assignee"),
        "task": task,
        "due_date": d.get("due_date"),
        "priority": pr,
        "status": status if status in ["Open","Doing","Done"] else "Open",
        "module": module,
        "phase": phase,
        "evidence_span": d.get("evidence_span") or task,
        "expected_effort": d.get("expected_effort"),
        "expected_value": d.get("expected_value"),
    }

def _fallback(text: str) -> List[Dict[str, Any]]:
    out = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if any(k in line for k in ["해야", "진행", "완료", "반영", "적용", "수정", "작성", "검증", "테스트"]):
            out.append({
                "assignee": None, "task": line, "due_date": None,
                "priority":"Medium","status":"Open","module":None,"phase":None,
                "evidence_span": line, "expected_effort": None, "expected_value": None
            })
        if len(out) >= 50: break
    return out