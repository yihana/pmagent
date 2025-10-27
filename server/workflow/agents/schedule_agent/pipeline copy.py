# pipeline.py (enhanced with PMP outputs)
import json
import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, date, timedelta
import csv
import logging

logger = logging.getLogger("schedule.agent")

try:
    import networkx as nx
    NX_AVAILABLE = True
except Exception:
    NX_AVAILABLE = False
    logger.warning("networkx not available: CPM critical path will be limited")

def _ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)
    return p

def _flatten_wbs_nodes(raw_wbs: Dict[str, Any]) -> List[Dict[str, Any]]:
    out = []
    def dfs(node, parent=None):
        nid = str(node.get("id") or node.get("name"))
        item = {
            "id": nid,
            "name": node.get("name") or node.get("title") or nid,
            "meta": node,
            "parent": str(parent) if parent is not None else None,
            "children": [str(c.get("id") or c.get("name")) for c in node.get("children", [])] if node.get("children") else []
        }
        out.append(item)
        for c in node.get("children", []) if node.get("children") else []:
            dfs(c, nid)
    for root in raw_wbs.get("nodes", []):
        dfs(root, None)
    return out

def _default_duration_estimator(tasks: List[Dict[str, Any]], methodology: str = "waterfall", sprint_length_weeks: int = 2) -> List[Dict[str, Any]]:
    out = []
    for t in tasks:
        name = t.get("name","")
        words = len(str(name).split())
        if methodology == "agile":
            sp = min(max(words, 1), 8)
            dur_days = sp
            sprint_days = sprint_length_weeks * 5
            if dur_days > sprint_days:
                dur_days = sprint_days
            out.append({"id": t["id"], "name": name, "duration": int(dur_days), "predecessors": [], "story_points": int(sp)})
        else:
            dur_days = max(1, min(5, words))
            out.append({"id": t["id"], "name": name, "duration": int(dur_days), "predecessors": []})
    return out

def _build_dependency_edges(tasks: List[Dict[str, Any]]) -> List[Tuple[str,str]]:
    edges = []
    id_map = {t['id']:t for t in tasks}
    for t in tasks:
        preds = t.get("predecessors") or []
        if isinstance(preds, str):
            preds = [p.strip() for p in preds.split(",") if p.strip()]
        for p in preds:
            if p in id_map:
                edges.append((p, t['id']))
    return edges

def _cpm_compute(tasks: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str,Any]]]:
    if not NX_AVAILABLE:
        logger.warning("NetworkX not available: skipping CPM compute")
        tasks_out = []
        for t in tasks:
            tasks_out.append({**t, "ES": 0, "EF": t.get("duration",1), "LS": None, "LF": None, "Float": None})
        return tasks_out, []
    
    G = nx.DiGraph()
    for t in tasks:
        G.add_node(t['id'], duration=float(t.get('duration',1)), name=t.get('name'))
    for t in tasks:
        preds = t.get('predecessors') or []
        if isinstance(preds, str):
            preds = [p.strip() for p in preds.split(",") if p.strip()]
        for p in preds:
            if p and p in G.nodes:
                G.add_edge(p, t['id'])
    
    if not nx.is_directed_acyclic_graph(G):
        logger.warning("Graph is not a DAG; attempting simple cleanup")
        try:
            cycles = list(nx.simple_cycles(G))
            for cyc in cycles:
                if len(cyc) >= 2:
                    u = cyc[-2]; v = cyc[-1]
                    if G.has_edge(u,v):
                        G.remove_edge(u,v)
        except Exception as e:
            logger.exception("Cycle cleanup failed: %s", e)
    
    for n in nx.topological_sort(G):
        preds = list(G.predecessors(n))
        es = max((G.nodes[p].get('EF',0) for p in preds), default=0)
        ef = es + G.nodes[n]['duration']
        G.nodes[n]['ES'] = es
        G.nodes[n]['EF'] = ef
    
    project_duration = max((G.nodes[n]['EF'] for n in G.nodes), default=0)
    
    for n in reversed(list(nx.topological_sort(G))):
        succs = list(G.successors(n))
        lf = min((G.nodes[s].get('LS', project_duration) for s in succs), default=project_duration)
        ls = lf - G.nodes[n]['duration']
        G.nodes[n]['LF'] = lf
        G.nodes[n]['LS'] = ls
        G.nodes[n]['Float'] = ls - G.nodes[n]['ES']
    
    tasks_out = []
    for n in G.nodes:
        nd = G.nodes[n]
        tasks_out.append({
            "id": n,
            "name": nd.get('name'),
            "duration": nd.get('duration'),
            "ES": nd.get('ES'),
            "EF": nd.get('EF'),
            "LS": nd.get('LS'),
            "LF": nd.get('LF'),
            "Float": nd.get('Float')
        })
    
    critical_nodes = [t for t in tasks_out if abs(float(t.get('Float',0))) < 1e-6]
    critical_nodes = sorted(critical_nodes, key=lambda x: x.get('ES',0))
    return tasks_out, critical_nodes

def _write_schedule_outputs(rows: List[Dict[str, Any]], critical_nodes: List[Dict[str,Any]], project_id: Any, out_root: Path) -> Dict[str, str]:
    proj = out_root / str(project_id)
    _ensure_dir(proj)
    
    csv_path = proj / "plan.csv"
    fields = set()
    for r in rows:
        fields.update(r.keys())
    fields = list(sorted(fields))
    
    with open(csv_path, "w", newline='', encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for r in rows:
            row = {}
            for k in fields:
                v = r.get(k)
                if isinstance(v, (list,tuple)):
                    row[k] = ",".join(map(str,v))
                else:
                    row[k] = v
            writer.writerow(row)
    
    gantt = {"project_id": str(project_id), "generated_at": datetime.utcnow().isoformat(), "tasks": []}
    for r in rows:
        gantt["tasks"].append({
            "id": r.get("id"),
            "name": r.get("name"),
            "start": r.get("start") if r.get("start") else None,
            "end": r.get("end") if r.get("end") else None,
            "duration": r.get("duration"),
            "predecessors": r.get("predecessors") or []
        })
    
    gantt_path = proj / "gantt.json"
    gantt_path.write_text(json.dumps(gantt, ensure_ascii=False, indent=2), encoding="utf-8")
    
    timeline = {"project_id": str(project_id), "tasks": [{"id":t.get("id"), "name":t.get("name"), "ES": t.get("ES"), "EF": t.get("EF")} for t in rows]}
    timeline_path = proj / "timeline.json"
    timeline_path.write_text(json.dumps(timeline, ensure_ascii=False, indent=2), encoding="utf-8")
    
    cp_path = proj / "critical_path.json"
    cp_content = {"project_id": str(project_id), "critical_path": critical_nodes}
    cp_path.write_text(json.dumps(cp_content, ensure_ascii=False, indent=2), encoding="utf-8")
    
    return {
        "plan_csv": str(csv_path),
        "gantt_json": str(gantt_path),
        "timeline": str(timeline_path),
        "critical_path": str(cp_path)
    }

def _generate_burndown(sprint_backlogs: List[Dict[str,Any]], start_date: date, sprint_length_weeks: int) -> Tuple[str, Dict[str,Any]]:
    days = sprint_length_weeks * 5
    burndown_points = []
    
    for sprint in sprint_backlogs:
        sprint_id = sprint.get("sprint_id")
        committed = int(sprint.get("committed_sp", 0))
        
        for d in range(days+1):
            remaining = max(0, committed - int((committed/days)*d)) if days>0 else committed
            burndown_points.append({
                "sprint_id": sprint_id, 
                "day": d, 
                "remaining_sp": int(remaining), 
                "date": (start_date + timedelta(days=d)).isoformat()
            })
    
    content = {"generated_at": datetime.utcnow().isoformat(), "burndown": burndown_points}
    return json.dumps(content, ensure_ascii=False, indent=2), content


class ScheduleAgent:
    def __init__(self, data_dir: Optional[str] = None):
        here = Path(__file__).resolve()
        root = here.parents[4] if len(here.parents) >=5 else here.parent
        self.DATA_DIR = Path(data_dir) if data_dir else (root / "data")
        self.OUT_DIR = self.DATA_DIR / "outputs" / "schedule"
        _ensure_dir(self.OUT_DIR)

    async def pipeline(self, payload: Any) -> Dict[str, Any]:
        if not isinstance(payload, dict):
            if hasattr(payload, "model_dump"):
                payload = payload.model_dump()
            elif hasattr(payload, "dict"):
                payload = payload.dict()
            else:
                payload = {}

        project_id = payload.get("project_id", "default")
        methodology = (payload.get("methodology") or "waterfall").lower()
        sprint_length_weeks = int(payload.get("sprint_length_weeks") or 2)
        estimation_mode = payload.get("estimation_mode") or "heuristic"
        wbs_src = payload.get("wbs_json")
        
        wbs = await self._load_wbs(wbs_src)
        nodes = _flatten_wbs_nodes(wbs)
        estimated = _default_duration_estimator(nodes, methodology=methodology, sprint_length_weeks=sprint_length_weeks)
        
        for t in estimated:
            meta = next((n["meta"] for n in nodes if n["id"] == t["id"]), {})
            meta_preds = meta.get("predecessors") or meta.get("depends") or meta.get("dependencies")
            if meta_preds:
                if isinstance(meta_preds, list):
                    t["predecessors"] = meta_preds
                elif isinstance(meta_preds, str):
                    t["predecessors"] = [p.strip() for p in meta_preds.split(",") if p.strip()]
        
        edges = _build_dependency_edges(estimated)
        if not edges:
            for n in nodes:
                if n.get("parent"):
                    edges.append((n['parent'], n['id']))
        
        rows_for_cpm = []
        id_set = {t['id'] for t in estimated}
        for t in estimated:
            preds = t.get('predecessors') or []
            preds = [p for p in preds if p in id_set]
            rows_for_cpm.append({
                "id": t['id'],
                "name": t['name'],
                "duration": t['duration'],
                "predecessors": preds,
                "story_points": t.get("story_points")
            })
        
        tasks_with_times, critical_nodes = _cpm_compute(rows_for_cpm)
        time_map = {t['id']: t for t in tasks_with_times}
        rows_out = []
        
        cal = payload.get("calendar") or {}
        start_date_str = cal.get("start_date")
        try:
            if start_date_str:
                start_date = datetime.fromisoformat(start_date_str).date()
            else:
                start_date = date.today()
        except Exception:
            start_date = date.today()
        
        for r in rows_for_cpm:
            tid = r['id']
            times = time_map.get(tid, {})
            ES = int(times.get("ES", 0))
            EF = int(times.get("EF", ES + r.get("duration",1)))
            planned_start = (start_date + timedelta(days=ES))
            planned_end = (start_date + timedelta(days=EF))
            row = {
                **r,
                "ES": ES,
                "EF": EF,
                "start": planned_start.isoformat(),
                "end": planned_end.isoformat(),
                "Float": times.get("Float")
            }
            rows_out.append(row)
        
        outputs = _write_schedule_outputs(rows_out, critical_nodes, project_id, self.OUT_DIR)
        
        burndown_path = None
        burndown_content = None
        sprint_count = None
        sprint_backlogs = payload.get("sprint_backlogs")
        
        if methodology == "agile":
            if not sprint_backlogs:
                sp_tasks = [t for t in rows_out if t.get("story_points")]
                total_sp = sum(int(t.get("story_points",0)) for t in sp_tasks)
                sprint_count = max(1, int((total_sp / (sprint_length_weeks*10)) + 0.999))
                
                sprint_backlogs = []
                remaining_sp = total_sp
                for i in range(sprint_count):
                    capacity = sprint_length_weeks * 10
                    assigned = min(capacity, remaining_sp)
                    sprint_backlogs.append({"sprint_id": i+1, "committed_sp": assigned})
                    remaining_sp -= assigned
            else:
                sprint_count = len(sprint_backlogs)
            
            burndown_json_str, burndown_content = _generate_burndown(sprint_backlogs, start_date, sprint_length_weeks)
            proj = self.OUT_DIR / str(project_id)
            _ensure_dir(proj)
            burndown_path = proj / "burndown.json"
            burndown_path.write_text(burndown_json_str, encoding="utf-8")
            burndown_path = str(burndown_path)
        
        # ✅ PMP 표준 산출물 생성
        pmp_outputs = await self._generate_pmp_outputs(
            project_id=project_id,
            project_dir=self.OUT_DIR / str(project_id),
            methodology=methodology
        )
        
        return {
            "status": "ok",
            "methodology": methodology,
            "plan_csv": outputs.get("plan_csv"),
            "gantt_json": outputs.get("gantt_json"),
            "critical_path": outputs.get("critical_path"),
            "burndown_json": burndown_path,
            # ✅ PMP 산출물
            **pmp_outputs,
            "data": {
                "project_id": project_id,
                "timeline_path": outputs.get("timeline"),
                "tasks": len(rows_out),
                "sprint_count": sprint_count
            },
            "message": None
        }

    async def _load_wbs(self, src: Optional[str]) -> Dict[str, Any]:
        if not src:
            return {"nodes": []}
        p = Path(src)
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                return {"nodes": []}
        try:
            return json.loads(src)
        except Exception:
            return {"nodes": []}
    
    async def _generate_pmp_outputs(
        self,
        project_id: str,
        project_dir: Path,
        methodology: str
    ) -> Dict[str, str]:
        """PMP 표준 산출물 생성"""
        from .outputs.change_mgmt import ChangeManagementGenerator
        
        outputs = {}
        
        try:
            # 변경관리 대장
            change_mgmt_path = project_dir / f"{project_id}_변경관리.xlsx"
            outputs["change_management_excel"] = ChangeManagementGenerator.generate(
                project_id=project_id,
                output_path=change_mgmt_path
            )
        except Exception as e:
            outputs["change_management_excel"] = f"Error: {e}"
        
        return outputs