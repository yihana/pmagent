# server/workflow/agents/schedule_agent/pipeline.py
# ScheduleAgent with CPM + Change Request support
from __future__ import annotations
import json
import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, date, timedelta
import csv
import logging
import copy

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
    out: List[Dict[str, Any]] = []

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
    out: List[Dict[str, Any]] = []
    for t in tasks:
        name = t.get("name", "")
        words = len(str(name).split())
        if methodology == "agile":
            # Story point-ish heuristic mapped to days (1 SP ~= 1 day here)
            sp = min(max(words, 1), 13)
            dur_days = sp
            sprint_days = sprint_length_weeks * 5
            if dur_days > sprint_days:
                dur_days = sprint_days
            out.append({"id": t["id"], "name": name, "duration": int(dur_days), "predecessors": [], "story_points": int(sp)})
        else:
            dur_days = max(1, min(10, max(1, int(words / 1))))
            out.append({"id": t["id"], "name": name, "duration": int(dur_days), "predecessors": []})
    return out


def _build_dependency_edges(tasks: List[Dict[str, Any]]) -> List[Tuple[str, str]]:
    edges: List[Tuple[str, str]] = []
    id_map = {t['id']: t for t in tasks}
    for t in tasks:
        preds = t.get("predecessors") or []
        if isinstance(preds, str):
            preds = [p.strip() for p in preds.split(",") if p.strip()]
        for p in preds:
            if p in id_map:
                edges.append((p, t['id']))
    return edges


def _cpm_compute(tasks: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    if not NX_AVAILABLE:
        logger.warning("NetworkX not available: skipping CPM compute")
        tasks_out = []
        for t in tasks:
            tasks_out.append({**t, "ES": 0, "EF": t.get("duration", 1), "LS": None, "LF": None, "Float": None})
        return tasks_out, []

    G = nx.DiGraph()
    for t in tasks:
        try:
            dur = float(t.get('duration', 1))
        except Exception:
            dur = 1.0
        G.add_node(t['id'], duration=dur, name=t.get('name'))

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
                # break last edge in cycle heuristically
                if len(cyc) >= 2:
                    u = cyc[-2]; v = cyc[-1]
                    if G.has_edge(u, v):
                        G.remove_edge(u, v)
                        logger.info("Removed edge %s->%s to break cycle", u, v)
        except Exception as e:
            logger.exception("Cycle cleanup failed: %s", e)

    for n in nx.topological_sort(G):
        preds = list(G.predecessors(n))
        es = max((G.nodes[p].get('EF', 0) for p in preds), default=0)
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

    tasks_out: List[Dict[str, Any]] = []
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

    critical_nodes = [t for t in tasks_out if abs(float(t.get('Float', 0) or 0)) < 1e-6]
    critical_nodes = sorted(critical_nodes, key=lambda x: x.get('ES', 0))
    return tasks_out, critical_nodes


def _write_schedule_outputs(rows: List[Dict[str, Any]], critical_nodes: List[Dict[str, Any]], project_id: Any, out_root: Path) -> Dict[str, str]:
    proj = out_root / str(project_id)
    _ensure_dir(proj)

    # write plan CSV
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
                if isinstance(v, (list, tuple)):
                    row[k] = ",".join(map(str, v))
                else:
                    row[k] = v
            writer.writerow(row)

    # write gantt JSON
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

    # write timeline
    timeline = {"project_id": str(project_id), "tasks": [{"id": t.get("id"), "name": t.get("name"), "ES": t.get("ES"), "EF": t.get("EF")} for t in rows]}
    timeline_path = proj / "timeline.json"
    timeline_path.write_text(json.dumps(timeline, ensure_ascii=False, indent=2), encoding="utf-8")

    # write critical path file
    cp_path = proj / "critical_path.json"
    cp_content = {"project_id": str(project_id), "critical_path": critical_nodes}
    cp_path.write_text(json.dumps(cp_content, ensure_ascii=False, indent=2), encoding="utf-8")

    # --- 안전한 critical_path 처리: cp_path 파일을 직접 읽어 파싱 (전역 state 의존 제거) ---
    parsed_cp: List[Any] = []
    try:
        if cp_path.exists():
            txt = cp_path.read_text(encoding="utf-8")
            try:
                data = json.loads(txt)
            except Exception:
                data = txt

            if isinstance(data, list):
                parsed_cp = data
            elif isinstance(data, dict) and "critical_path" in data and isinstance(data["critical_path"], list):
                parsed_cp = data["critical_path"]
            else:
                parsed_cp = [data]
        else:
            parsed_cp = []
    except Exception as e:
        logger.exception("[SCHEDULE] failed to load/parse critical_path file %s: %s", cp_path, e)
        parsed_cp = []

    # 반환: 기존 호환성(파일 경로) 유지 + 내부 사용/DB 저장용으로 파싱된 결과 제공
    return {
        "plan_csv": str(csv_path),
        "gantt_json": str(gantt_path),
        "timeline": str(timeline_path),
        "critical_path": str(cp_path),
        "_parsed_critical_path": parsed_cp
    }


def _generate_burndown(sprint_backlogs: List[Dict[str, Any]], start_date: date, sprint_length_weeks: int) -> Tuple[str, Dict[str, Any]]:
    days = sprint_length_weeks * 5
    burndown_points = []

    for sprint in sprint_backlogs:
        sprint_id = sprint.get("sprint_id")
        committed = int(sprint.get("committed_sp", 0))

        for d in range(days + 1):
            remaining = max(0, committed - int((committed / days) * d)) if days > 0 else committed
            burndown_points.append({
                "sprint_id": sprint_id,
                "day": d,
                "remaining_sp": int(remaining),
                "date": (start_date + timedelta(days=d)).isoformat()
            })

    content = {"generated_at": datetime.utcnow().isoformat(), "burndown": burndown_points}
    return json.dumps(content, ensure_ascii=False, indent=2), content


# ----------------------------
# Change Request apply helper
# ----------------------------
def _apply_change_requests(tasks: List[Dict[str, Any]], change_requests: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Apply change requests to the task list.
    change_request format examples:
      { "op":"update_duration", "task_id":"WBS-1.1", "new_duration": 5 }
      { "op":"add_pred", "task_id":"WBS-1.2", "predecessor":"WBS-1.1" }
      { "op":"remove_pred", "task_id":"WBS-1.2", "predecessor":"WBS-1.1" }
      { "op":"set_predecessors", "task_id":"WBS-1.3", "predecessors":["WBS-1.2","WBS-1.1"] }
      { "op":"update_name", "task_id":"WBS-1.3", "new_name":"Refined name" }
    Returns: (updated_tasks, change_log)
    """
    id_map = {t['id']: t for t in tasks}
    change_log: List[Dict[str, Any]] = []
    tasks_copy = copy.deepcopy(tasks)
    for cr in change_requests or []:
        op = cr.get("op")
        tid = cr.get("task_id")
        if not tid or tid not in id_map:
            change_log.append({"ok": False, "reason": f"task_id missing or unknown: {tid}", "cr": cr})
            continue
        t = next((x for x in tasks_copy if x['id'] == tid), None)
        if t is None:
            change_log.append({"ok": False, "reason": f"task_id not found in copy: {tid}", "cr": cr})
            continue

        if op == "update_duration":
            new_d = cr.get("new_duration")
            try:
                t['duration'] = int(new_d)
                change_log.append({"ok": True, "op": op, "task_id": tid, "new_duration": t['duration']})
            except Exception as e:
                change_log.append({"ok": False, "op": op, "task_id": tid, "error": str(e)})
        elif op == "add_pred":
            pred = cr.get("predecessor")
            if not pred:
                change_log.append({"ok": False, "reason": "missing predecessor", "cr": cr})
                continue
            preds = t.get("predecessors") or []
            if isinstance(preds, str):
                preds = [p.strip() for p in preds.split(",") if p.strip()]
            if pred not in preds:
                preds.append(pred)
            t['predecessors'] = preds
            change_log.append({"ok": True, "op": op, "task_id": tid, "predecessors": preds})
        elif op == "remove_pred":
            pred = cr.get("predecessor")
            preds = t.get("predecessors") or []
            if isinstance(preds, str):
                preds = [p.strip() for p in preds.split(",") if p.strip()]
            if pred in preds:
                preds.remove(pred)
            t['predecessors'] = preds
            change_log.append({"ok": True, "op": op, "task_id": tid, "predecessors": preds})
        elif op == "set_predecessors":
            preds = cr.get("predecessors") or []
            t['predecessors'] = preds
            change_log.append({"ok": True, "op": op, "task_id": tid, "predecessors": preds})
        elif op == "update_name":
            t['name'] = cr.get("new_name") or t.get("name")
            change_log.append({"ok": True, "op": op, "task_id": tid, "new_name": t['name']})
        else:
            change_log.append({"ok": False, "reason": "unknown op", "op": op, "cr": cr})
    return tasks_copy, change_log


class ScheduleAgent:
    def __init__(self, data_dir: Optional[str] = None):
        here = Path(__file__).resolve()
        root = here.parents[4] if len(here.parents) >= 5 else here.parent
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
        change_requests = payload.get("change_requests")  # new: list of CR dicts

        wbs = await self._load_wbs(wbs_src)
        nodes = _flatten_wbs_nodes(wbs)
        estimated = _default_duration_estimator(nodes, methodology=methodology, sprint_length_weeks=sprint_length_weeks)

        # preserve meta predecessors if present
        for t in estimated:
            meta = next((n["meta"] for n in nodes if n["id"] == t["id"]), {})
            meta_preds = meta.get("predecessors") or meta.get("depends") or meta.get("dependencies")
            if meta_preds:
                if isinstance(meta_preds, list):
                    t["predecessors"] = meta_preds
                elif isinstance(meta_preds, str):
                    t["predecessors"] = [p.strip() for p in meta_preds.split(",") if p.strip()]

        # Build edges if none present using parent -> child
        edges = _build_dependency_edges(estimated)
        if not edges:
            for n in nodes:
                if n.get("parent"):
                    edges.append((n['parent'], n['id']))

        rows_for_cpm: List[Dict[str, Any]] = []
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

        # baseline compute
        tasks_with_times, critical_nodes = _cpm_compute(rows_for_cpm)
        time_map = {t['id']: t for t in tasks_with_times}
        rows_out: List[Dict[str, Any]] = []

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
            ES = int(times.get("ES", 0) or 0)
            EF = int(times.get("EF", ES + r.get("duration", 1)) or (ES + r.get("duration", 1)))
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
                total_sp = sum(int(t.get("story_points", 0)) for t in sp_tasks)
                sprint_count = max(1, int((total_sp / (sprint_length_weeks * 10)) + 0.999))

                sprint_backlogs = []
                remaining_sp = total_sp
                for i in range(sprint_count):
                    capacity = sprint_length_weeks * 10
                    assigned = min(capacity, remaining_sp)
                    sprint_backlogs.append({"sprint_id": i + 1, "committed_sp": assigned})
                    remaining_sp -= assigned
            else:
                sprint_count = len(sprint_backlogs)

            burndown_json_str, burndown_content = _generate_burndown(sprint_backlogs, start_date, sprint_length_weeks)
            proj = self.OUT_DIR / str(project_id)
            _ensure_dir(proj)
            burndown_path = proj / "burndown.json"
            burndown_path.write_text(burndown_json_str, encoding="utf-8")
            burndown_path = str(burndown_path)

        # PMP 표준 산출물 생성 (baseline)
        pmp_outputs = await self._generate_pmp_outputs(
            project_id=project_id,
            project_dir=self.OUT_DIR / str(project_id),
            methodology=methodology
        )

        result: Dict[str, Any] = {
            "status": "ok",
            "methodology": methodology,
            "plan_csv": outputs.get("plan_csv"),
            "gantt_json": outputs.get("gantt_json"),
            "critical_path": outputs.get("critical_path"),
            "timeline": outputs.get("timeline"),
            "burndown_json": burndown_path,
            # PMP outputs
            **pmp_outputs,
            "data": {
                "project_id": project_id,
                "timeline_path": outputs.get("timeline"),
                "tasks": len(rows_out),
                "sprint_count": sprint_count
            },
            "message": None,
            # internal baseline details
            "_internal": {
                "rows_out": rows_out,
                "critical_nodes": critical_nodes
            },
            # parsed critical path (for immediate consumption / DB storage if needed)
            "_parsed_critical_path": outputs.get("_parsed_critical_path", [])
        }

        # -------------------------
        #  Change Requests 처리 (옵션)
        # -------------------------
        if change_requests:
            try:
                updated_rows_for_cpm, change_log = _apply_change_requests(rows_for_cpm, change_requests)
                # recompute CPM with updated_rows_for_cpm
                tasks_with_times2, critical_nodes2 = _cpm_compute(updated_rows_for_cpm)
                time_map2 = {t['id']: t for t in tasks_with_times2}
                rows_out2: List[Dict[str, Any]] = []
                for r in updated_rows_for_cpm:
                    tid = r['id']
                    times = time_map2.get(tid, {})
                    ES = int(times.get("ES", 0) or 0)
                    EF = int(times.get("EF", ES + r.get("duration", 1)) or (ES + r.get("duration", 1)))
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
                    rows_out2.append(row)

                # write revised outputs
                revised_outputs = _write_schedule_outputs(rows_out2, critical_nodes2, f"{project_id}_revised", self.OUT_DIR)

                # generate change mgmt (sheet) reflecting the CRs
                try:
                    pmp_cr_outputs = await self._generate_pmp_outputs_cr(
                        project_id=project_id,
                        project_dir=self.OUT_DIR / str(project_id),
                        methodology=methodology,
                        change_log=change_log
                    )
                except Exception as e:
                    logger.exception("Failed to generate CR PMP outputs: %s", e)
                    pmp_cr_outputs = {"change_management_excel": f"Error: {e}"}

                # attach CR results
                result["change_requests"] = {
                    "applied": change_log,
                    "revised_plan_csv": revised_outputs.get("plan_csv"),
                    "revised_gantt_json": revised_outputs.get("gantt_json"),
                    "revised_critical_path": revised_outputs.get("critical_path"),
                    "revised_timeline": revised_outputs.get("timeline"),
                    "pmp_cr_outputs": pmp_cr_outputs
                }
            except Exception as e:
                logger.exception("CR apply failed: %s", e)
                result["change_requests"] = {"error": str(e)}

        return result

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
        """PMP 표준 산출물 생성 (baseline)"""
        # import here to avoid heavy imports during module load
        try:
            from .outputs.change_mgmt import ChangeManagementGenerator
        except Exception:
            # backward compatibility: module might be named change_management earlier
            try:
                from .outputs.change_management import ChangeManagementGenerator
            except Exception:
                ChangeManagementGenerator = None

        outputs: Dict[str, Optional[str]] = {}

        try:
            if ChangeManagementGenerator is not None:
                change_mgmt_path = project_dir / f"{project_id}_변경관리.xlsx"
                outputs["change_management_excel"] = ChangeManagementGenerator.generate(
                    project_id=project_id,
                    output_path=change_mgmt_path
                )
            else:
                outputs["change_management_excel"] = None
        except Exception as e:
            outputs["change_management_excel"] = f"Error: {e}"

        return outputs

    async def _generate_pmp_outputs_cr(
        self,
        project_id: str,
        project_dir: Path,
        methodology: str,
        change_log: List[Dict[str, Any]]
    ) -> Dict[str, str]:
        """PMP outputs specific to change requests (e.g. annotate change management)"""
        try:
            from .outputs.change_mgmt import ChangeManagementGenerator
        except Exception:
            try:
                from .outputs.change_management import ChangeManagementGenerator
            except Exception:
                ChangeManagementGenerator = None

        outputs: Dict[str, Optional[str]] = {}
        try:
            if ChangeManagementGenerator is not None:
                # We can pass change_log into generator if extended; for now generator writes sample sheet
                change_mgmt_path = project_dir / f"{project_id}_변경관리_CR.xlsx"
                outputs["change_management_excel"] = ChangeManagementGenerator.generate(
                    project_id=project_id,
                    output_path=change_mgmt_path
                )
            else:
                outputs["change_management_excel"] = None
        except Exception as e:
            outputs["change_management_excel"] = f"Error: {e}"
        return outputs
