# server/workflow/pm_graph.py
import asyncio
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, List

logger = logging.getLogger("pm.graph")

# -------- Optional analyzer (graceful fallback) --------
try:
    from server.workflow.agents import analyzer  # type: ignore
    _ANALYZER_AVAILABLE = True
except Exception as e:
    logger.warning("[ANALYZER] import failed: %s", e)
    analyzer = None
    _ANALYZER_AVAILABLE = False

# -------- ScopeAgent (robust import) --------
try:
    from server.workflow.agents.scope_agent.pipeline import ScopeAgent  # type: ignore
    _SCOPE_AVAILABLE = True
except Exception as e:
    logger.warning("[SCOPE_AGENT] import failed: %s", e)
    ScopeAgent = None
    _SCOPE_AVAILABLE = False

# -------- ScheduleAgent (robust import) --------
try:
    from server.workflow.agents.schedule_agent.pipeline import ScheduleAgent  # type: ignore
    _SCHEDULE_AVAILABLE = True
except Exception as e:
    logger.warning("[SCHEDULE_AGENT] import failed: %s", e)
    ScheduleAgent = None
    _SCHEDULE_AVAILABLE = False

def _resolve_data_dir() -> Path:
    # server/ 또는 프로젝트 루트 어디서든 동작
    here = Path(__file__).resolve()
    for p in here.parents:
        if (p / "data").exists():
            return p / "data"
    return here.parents[1] / "data"
DATA_DIR = _resolve_data_dir()

# ---------------- Handlers ----------------
async def _analyze_handler(payload: Dict[str, Any]) -> Dict[str, Any]:
    text = payload.get("text") or ""
    title = payload.get("title") or "Untitled"
    project_id = payload.get("project_id")
    result: Dict[str, Any] = {"project_id": project_id, "title": title, "action_items": []}
    if not _ANALYZER_AVAILABLE or analyzer is None:
        logger.info("[ANALYZE] analyzer not available; empty result")
        return result
    try:
        items = await asyncio.to_thread(analyzer.analyze_minutes, text)  # type: ignore
        result["action_items"] = items or []
    except Exception as e:
        logger.exception("[ANALYZE] failure: %s", e)
    return result

async def _report_handler(payload: Dict[str, Any]) -> Dict[str, Any]:
    # DB 의존 없이 가벼운 스텁
    fast = bool(payload.get("fast"))
    project_id = payload.get("project_id")
    return {
        "project_id": project_id,
        "fast": fast,
        "summary": "Auto-generated weekly report",
        "highlights": [],
    }

async def _scope_handler(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not _SCOPE_AVAILABLE or ScopeAgent is None:
        raise RuntimeError("ScopeAgent not available. Check server/workflow/agents/scope_agent/pipeline.py")
    agent = ScopeAgent(data_dir=str(DATA_DIR))
    return await agent.pipeline(payload)

async def _scope_summary_handler(payload: Dict[str, Any]) -> Dict[str, Any]:
    project_id = payload.get("project_id")
    out_dir = Path(DATA_DIR) / "outputs" / "scope" / str(project_id)
    info = {"project_id": project_id, "exists": out_dir.exists(), "files": []}
    if out_dir.exists():
        for p in sorted(out_dir.glob("*")):
            info["files"].append({"name": p.name, "size": p.stat().st_size})
    return info

async def _schedule_handler(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not _SCHEDULE_AVAILABLE or ScheduleAgent is None:
        return {"warn": "ScheduleAgent not available; returning empty schedule", "timeline": []}
    agent = ScheduleAgent(data_dir=str(DATA_DIR))
    return await agent.pipeline(payload)

async def _schedule_timeline_handler(payload: Dict[str, Any]) -> Dict[str, Any]:
    project_id = payload.get("project_id")
    out_dir = Path(DATA_DIR) / "outputs" / "schedule" / str(project_id)
    f = out_dir / "timeline.json"
    if f.exists():
        return {"project_id": project_id, "timeline_path": str(f), "size": f.stat().st_size}
    return {"project_id": project_id, "timeline_path": None}

async def _workflow_scope_then_schedule_handler(payload: Dict[str, Any]) -> Dict[str, Any]:
    scope_result = await _scope_handler(payload)
    wbs_json_path = scope_result.get("wbs_json_path")
    sched_payload = {"project_id": payload.get("project_id"), "wbs_json": wbs_json_path}
    sched_result = await _schedule_handler(sched_payload)
    return {"scope": scope_result, "schedule": sched_result}

# ---------------- App / Pipeline ----------------
@dataclass
class _App:
    kind: str
    def __init__(self, kind: str):
        # ✅ bugfix: __init__ (예전 코드의 init 오타 수정)
        self.kind = kind
        if kind == "analyze":
            self.handler = _analyze_handler
        elif kind == "report":
            self.handler = _report_handler
        elif kind == "scope":
            self.handler = _scope_handler
        elif kind == "scope_summary":
            self.handler = _scope_summary_handler
        elif kind == "schedule":
            self.handler = _schedule_handler
        elif kind == "schedule_timeline":
            self.handler = _schedule_timeline_handler
        elif kind == "workflow_scope_then_schedule":
            self.handler = _workflow_scope_then_schedule_handler
        else:
            raise ValueError(f"unknown pipeline kind: {kind}")

    async def ainvoke(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return await self.handler(payload)

async def run_pipeline(kind: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    app = _App(kind)
    return await app.ainvoke(payload)
