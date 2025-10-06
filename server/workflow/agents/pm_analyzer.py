# server/workflow/agents/pm_analyzer.py
from __future__ import annotations

import json, re
from typing import Any, Dict, List, Optional

from server.utils.config import get_llm

ACTION_ITEM_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "assignee": {"type": ["string", "null"]},
            "task": {"type": "string"},
            "due_date": {"type": ["string", "null"]},
            "priority": {"type": "string", "enum": ["Low", "Medium", "High"]},
            "status": {"type": "string", "enum": ["Open", "In Progress", "Done", "Blocked"]},
            "module": {"type": ["string", "null"]},
            "phase": {"type": ["string", "null"]},
            "evidence_span": {"type": ["string", "null"]},
            "expected_effort": {"type": ["string", "null"]},
            "expected_value": {"type": ["string", "null"]},
        },
        "required": ["task"],
        "additionalProperties": True,
    },
}

def _json_first(text: str) -> Optional[str]:
    m = re.search(r"```json\s*(\{.*?\}|\[.*?\])\s*```", text, re.S | re.I)
    if m: return m.group(1)
    m = re.search(r"(\[.*?\])", text, re.S)
    if m: return m.group(1)
    m = re.search(r"(\{.*?\})", text, re.S)
    if m: return m.group(1)
    return None

def _normalize(d: Dict[str, Any], original: str) -> Dict[str, Any]:
    task = (d.get("task") or "").strip() or (original.splitlines()[0][:60] if original else "TBD")
    pr = (d.get("priority") or "Medium").capitalize()
    if pr not in ["Low", "Medium", "High"]: pr = "Medium"
    status = (d.get("status") or "Open").title()
    module = d.get("module")
    phase = d.get("phase")
    if not module:
        m = re.search(r"\b(FI|SD|MM|PP|EWM|HR|CRM)\b", task, re.I)
        module = m.group(1).upper() if m else None
    if not phase:
        p = re.search(r"(요구|설계|개발|테스트|인수|운영)", task)
        phase = p.group(1) if p else None
    return {
        "assignee": d.get("assignee"),
        "task": task,
        "due_date": d.get("due_date"),
        "priority": pr,
        "status": status,
        "module": module,
        "phase": phase,
        "evidence_span": d.get("evidence_span"),
        "expected_effort": d.get("expected_effort"),
        "expected_value": d.get("expected_value"),
    }

def _fallback_rules(text: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for line in text.splitlines():
        s = line.strip()
        if not s: continue
        if any(k in s for k in ["해야", "진행", "완료", "반영", "적용", "수정", "작성", "검증", "테스트"]):
            out.append(_normalize({"task": s}, text))
            if len(out) >= 50: break
    return out

def _postprocess(json_text: str, original: str) -> List[Dict[str, Any]]:
    try:
        arr = json.loads(json_text)
        if isinstance(arr, list):
            return [_normalize(x, original) for x in arr][:200]
        if isinstance(arr, dict) and isinstance(arr.get("items"), list):
            return [_normalize(x, original) for x in arr["items"]][:200]
    except Exception:
        pass
    return _fallback_rules(original)

def _make_system_prompt(doc_kind: str) -> str:
    return (
        "You are an expert PM analyst. "
        "Extract concrete action items from the given {kind} content. "
        "Answer in strict JSON ONLY (UTF-8, no markdown fences). "
        "Use the following JSON schema:\n"
        f"{json.dumps(ACTION_ITEM_SCHEMA, ensure_ascii=False)}"
    ).format(kind=doc_kind)

def _make_user_prompt(text: str, project_meta: Optional[Dict[str, Any]] = None) -> str:
    meta = project_meta or {}
    meta_str = json.dumps(meta, ensure_ascii=False)
    return (
        f"[PROJECT_META]\n{meta_str}\n\n"
        "[CONTENT]\n"
        f"{text}\n\n"
        "Return ONLY the JSON array. No extra text."
    )

class PM_AnalyzerAgent:
    """추상 상속 없이 동작하는 구체 구현"""
    def __init__(self, model_name: str = "gpt-4o", temperature: float = 0.2):
        self.model_name = model_name
        self.temperature = temperature
        self.llm = get_llm(model_name=model_name, temperature=temperature)

    def _run(self, doc_kind: str, text: str, project_meta: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        sys_prompt = _make_system_prompt(doc_kind)
        user_prompt = _make_user_prompt(text, project_meta)
        try:
            messages = [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_prompt},
            ]
            resp = self.llm.invoke(messages)
            content = getattr(resp, "content", None) or str(resp)
        except Exception:
            try:
                prompt = sys_prompt + "\n\n" + user_prompt
                content = self.llm.invoke(prompt)
                content = getattr(content, "content", None) or str(content)
            except Exception:
                return _fallback_rules(text)
        j = _json_first(content or "")
        if not j:
            return _fallback_rules(text)
        return _postprocess(j, text)

    def analyze_minutes(self, text: str, project_meta: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        return self._run("meeting minutes", text, project_meta)

    def analyze_rfp(self, text: str, project_meta: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        return self._run("RFP", text, project_meta)

    def analyze_proposal(self, text: str, project_meta: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        return self._run("proposal", text, project_meta)

    def analyze_issue(self, text: str, project_meta: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        return self._run("issue log", text, project_meta)
