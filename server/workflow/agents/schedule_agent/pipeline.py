import json, asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional

def _find_root(start: Path) -> Path:
    for p in start.parents:
        if (p / "data").exists():
            return p
    return start.parents[4]

class ScheduleAgent:
    """
    input: wbs_json (path or raw json)
    output: outputs/schedule/{project_id}/timeline.json
    """
    def __init__(self, data_dir: Optional[str] = None):
        here = Path(__file__).resolve()
        root = _find_root(here)
        self.DATA_DIR = Path(data_dir) if data_dir else (root / "data")
        self.OUT_DIR = self.DATA_DIR / "outputs" / "schedule"
        self.OUT_DIR.mkdir(parents=True, exist_ok=True)

    async def pipeline(self, payload: Any) -> Dict[str, Any]:
        # 방어적 표준화
        if not isinstance(payload, dict):
            if hasattr(payload, "model_dump"):
                payload = payload.model_dump()
            elif hasattr(payload, "dict"):
                payload = payload.dict()
            else:
                payload = {}

        project_id = payload.get("project_id", "default")
        wbs_json = payload.get("wbs_json")
        wbs = await self._load_wbs(wbs_json)
        timeline = await self._build_timeline(wbs)
        out = await self._write_timeline(project_id, timeline)
        return {"project_id": project_id, "timeline_path": str(out), "tasks": len(timeline)}

    async def _load_wbs(self, src: Optional[str]) -> Dict[str, Any]:
        if not src:
            return {"nodes": []}
        p = Path(src)
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
        try:
            return json.loads(src)
        except Exception:
            return {"nodes": []}

    async def _build_timeline(self, wbs: Dict[str, Any]) -> List[Dict[str, Any]]:
        tasks: List[Dict[str, Any]] = []
        day = 0
        def dfs(node: Dict[str, Any]):
            nonlocal day
            if node.get("children"):
                for c in node["children"]:
                    dfs(c)
            else:
                day += 1
                tasks.append({"id": node.get("id"), "name": node.get("name"),
                              "start_offset_days": day, "duration_days": 1})
        for root in wbs.get("nodes", []):
            dfs(root)
        await asyncio.sleep(0)
        return tasks

    async def _write_timeline(self, project_id: Any, timeline: List[Dict[str, Any]]) -> Path:
        proj = self.OUT_DIR / str(project_id)
        proj.mkdir(parents=True, exist_ok=True)
        out = proj / "timeline.json"
        out.write_text(json.dumps(timeline, ensure_ascii=False, indent=2), encoding="utf-8")
        return out
