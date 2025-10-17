import json
import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional


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
        2. extract_items: 요구사항 추출
        3. synthesize_wbs: WBS 구조 생성
        4. write_outputs: 파일로 저장
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
        """메인 파이프라인 실행"""
        if not isinstance(payload, dict):
            if hasattr(payload, "model_dump"):
                payload = payload.model_dump()
            elif hasattr(payload, "dict"):
                payload = payload.dict()
            else:
                payload = {}

        project_id = payload.get("project_id", "default")
        text = payload.get("text")
        rfp_filename = payload.get("rfp_filename")
        depth = int(payload.get("options", {}).get("wbs_depth", 3))

        raw = await self._ingest(text, rfp_filename)
        items = await self._extract_items(raw)
        wbs = await self._synthesize_wbs(items, depth)
        paths = await self._write_outputs(project_id, raw, items, wbs)
        
        return {
            "project_id": project_id,
            "wbs_json_path": str(paths["wbs_json"]),
            "rtm_csv_path": str(paths["rtm_csv"]),
            "scope_md_path": str(paths["scope_md"]),
            "stats": {
                "items": len(items), 
                "wbs_nodes": len(wbs.get("nodes", []))
            },
        }

    async def _ingest(self, text: Optional[str], rfp_filename: Optional[str]) -> str:
        """RFP 텍스트 로드"""
        if text:
            return text
        if rfp_filename:
            pdf = self.INPUT_RFP_DIR / rfp_filename
            if pdf.exists():
                return f"RFP: {pdf.name}\n\nOverview\nRequirements\nDeliverables"
            else:
                return f"[WARN] RFP not found: {pdf}"
        return "No input provided."

    async def _extract_items(self, raw: str) -> List[Dict[str, Any]]:
        """요구사항 추출 (간단한 줄 단위 파싱)"""
        items = []
        for i, ln in enumerate([l.strip() for l in raw.splitlines() if l.strip()], 1):
            items.append({
                "id": f"R{i:03d}",
                "text": ln,
                "type": "req" if "require" in ln.lower() else "note"
            })
        await asyncio.sleep(0)
        return items

    async def _synthesize_wbs(self, items: List[Dict[str, Any]], depth: int) -> Dict[str, Any]:
        """WBS 구조 생성"""
        nodes = [{"id": "WBS-1", "name": "Project", "level": 1, "children": []}]
        phases = [
            {"id": f"WBS-1.{i}", "name": f"Phase {i}", "level": 2, "children": []} 
            for i in range(1, 4)
        ]
        nodes[0]["children"] = phases
        
        t = 0
        for p in phases:
            for j in range(1, 4):
                t += 1
                p["children"].append({
                    "id": f"{p['id']}.{j}",
                    "name": f"Task {t}",
                    "level": 3
                })
        
        return {"nodes": nodes, "depth": max(1, min(depth, 3))}

    async def _write_outputs(
        self, 
        project_id: Any, 
        raw: str, 
        items: List[Dict[str, Any]], 
        wbs: Dict[str, Any]
    ) -> Dict[str, Path]:
        """결과 파일 저장"""
        proj_dir = self.OUT_DIR / str(project_id)
        proj_dir.mkdir(parents=True, exist_ok=True)
        
        # WBS JSON
        wbs_json = proj_dir / "wbs_structure.json"
        wbs_json.write_text(
            json.dumps(wbs, ensure_ascii=False, indent=2), 
            encoding="utf-8"
        )
        
        # RTM CSV
        rtm_csv = proj_dir / "rtm.csv"
        with open(rtm_csv, "w", encoding="utf-8", newline="") as f:
            f.write("req_id,text,type\n")
            for it in items:
                text_safe = it['text'].replace(',', ';').replace('\n', ' ')
                f.write(f"{it['id']},{text_safe},{it['type']}\n")
        
        # Scope Statement Markdown
        scope_md = proj_dir / "scope_statement.md"
        with open(scope_md, "w", encoding="utf-8") as f:
            f.write("# Scope Statement\n\n")
            f.write("## Overview\n\n")
            f.write(raw + "\n\n")
            f.write("## WBS\n\n")
            f.write("```json\n")
            f.write(json.dumps(wbs, ensure_ascii=False, indent=2))
            f.write("\n```\n")
        
        return {
            "wbs_json": wbs_json,
            "rtm_csv": rtm_csv,
            "scope_md": scope_md
        }