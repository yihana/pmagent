# server/workflow/agents/schedule_agent/pipeline.py
# ScheduleAgent with CPM + Change Request support
from __future__ import annotations
import os, re, json, asyncio, time, logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, date, timedelta
import csv
import copy

from server.utils.config import get_llm
from server.workflow.agents.schedule_agent.prompts import RTM_PROMPT, WBS_ENRICH_PROMPT, CHANGE_MGMT_PROMPT

from server.workflow.agents.scope_agent.outputs.rtm_excel import RTMExcelGenerator
from server.workflow.agents.scope_agent.outputs.wbs_excel import WBSExcelGenerator
from server.workflow.agents.schedule_agent.outputs.change_mgmt import ChangeManagementGenerator


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
    # 1111
    return {
        "plan_csv": str(csv_path),
        "gantt_json": str(gantt_path),
        "timeline": str(timeline_path),
        "critical_path": str(cp_path),
        "_parsed_critical_path": parsed_cp,
        # ✅ ScopeAgent 결과 참조 경로
        "scope_requirements_json": str(
            Path(out_root).parent / "scope" / str(project_id) / "requirements.json"
        )
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

# ---- Replace existing ScheduleAgent class with this block ----
class ScheduleAgent:
    def __init__(self, data_dir: str = "data/outputs/schedule"):
        self.llm = get_llm()
        self.DATA_DIR = Path(data_dir)
        self.OUT_DIR = self.DATA_DIR
        self.OUT_DIR.mkdir(parents=True, exist_ok=True)

        # LLM support (optional)
        self.llm = self._get_llm()
        self.llm_timeout = int(os.getenv("SCHEDULE_LLM_TIMEOUT", "300"))
        logger.info(f"[SCHEDULE_AGENT] initialized - DATA_DIR: {self.DATA_DIR}, llm_timeout={self.llm_timeout}s, llm_available={bool(self.llm)}")

    def _get_llm(self):
        """
        Try to import/get LLM similar to ScopeAgent.get_llm.
        Returns None if not available.
        """
        try:
            from server.utils.config import get_llm as _g
            llm = _g()
            logger.debug("[SCHEDULE] get_llm() success: %s", getattr(llm, "__class__", llm))
            return llm
        except Exception as e:
            logger.debug("[SCHEDULE] get_llm failed: %s", e)
            return None

    async def _call_llm_with_timeout(self, prompt: str, project_id: Any, attempt: int = 1) -> Optional[str]:
        """
        Call the configured LLM with timeout and backoff; save raw response for debugging.
        Returns text content or None on failure.
        """
        if not self.llm:
            return None

        def call():
            try:
                # support multiple LLM client shapes
                if hasattr(self.llm, "invoke"):
                    messages = [
                        {"role": "system", "content": "You are a scheduling analyst. Return valid JSON as requested."},
                        {"role": "user", "content": prompt}
                    ]
                    return self.llm.invoke(messages)
                elif hasattr(self.llm, "generate"):
                    return self.llm.generate(prompt)
                elif callable(self.llm):
                    return self.llm(prompt)
                return None
            except Exception as e:
                logger.error("[SCHEDULE] LLM sync call exception: %s", e)
                raise

        try:
            resp = await asyncio.wait_for(asyncio.to_thread(call), timeout=self.llm_timeout)
        except asyncio.TimeoutError:
            logger.warning("[SCHEDULE] LLM call timeout (%ds) on attempt %d", self.llm_timeout, attempt)
            return None
        except Exception as e:
            logger.warning("[SCHEDULE] LLM call exception on attempt %d: %s", attempt, e)
            return None

        # extract text similar to scope helper (copied minimal)
        text = ""
        try:
            if resp is None:
                text = ""
            elif isinstance(resp, str):
                text = resp
            elif hasattr(resp, "generations"):
                gens = getattr(resp, "generations")
                if isinstance(gens, list) and len(gens) and hasattr(gens[0], "message"):
                    text = gens[0].message.content
                else:
                    text = str(resp)
            elif hasattr(resp, "choices"):
                c = resp.choices
                first = c[0]
                if hasattr(first, "message"):
                    content = first.message
                    if isinstance(content, dict):
                        text = content.get("content", "") or str(content)
                    elif hasattr(content, "get"):
                        text = content.get("content", "")
                    elif hasattr(content, "content"):
                        text = content.content
                    else:
                        text = str(content)
                elif hasattr(first, "text"):
                    text = getattr(first, "text", "")
                else:
                    text = str(first)
            elif hasattr(resp, "content"):
                text = getattr(resp, "content")
            else:
                text = str(resp)
        except Exception as e:
            logger.debug("[SCHEDULE] LLM response extraction failed: %s", e)
            text = str(resp)

        # save raw response for debugging
        try:
            dbg_dir = Path(self.OUT_DIR) / "dbg" / str(project_id)
            dbg_dir.mkdir(parents=True, exist_ok=True)
            dbg_file = dbg_dir / f"llm_raw_attempt{attempt}_{int(time.time())}.txt"
            dbg_file.write_text(str(text), encoding="utf-8", errors="ignore")
            logger.info("[SCHEDULE] Saved raw LLM response: %s", dbg_file)
        except Exception as e:
            logger.debug("[SCHEDULE] failed to save raw llm response: %s", e)

        return text

    async def _estimate_durations_via_llm(self, nodes: List[Dict[str, Any]], methodology: str, project_id: Any) -> List[Dict[str, Any]]:
        """
        Ask LLM to estimate duration_days and predecessors for nodes.
        Expected LLM output: JSON array of objects [{id, duration_days, predecessors: [id,...]}, ...]
        If LLM fails or parse fails, return empty list (caller should fallback to heuristic).
        """
        try:
            # import schedule prompts
            try:
                from .prompts import DURATION_DEP_PROMPT
            except Exception:
                DURATION_DEP_PROMPT = "Input: {wbs_json}\nReturn: JSON array [{id,duration_days,predecessors:[..]}]"

            # small WBS JSON for prompt - include nodes minimal fields
            wbs_obj = {"nodes": []}
            for n in nodes:
                # include id, name, parent, children count
                wbs_obj["nodes"].append({"id": n.get("id"), "name": n.get("name"), "parent": n.get("parent")})

            prompt = DURATION_DEP_PROMPT.format(methodology=methodology, wbs_json=json.dumps(wbs_obj, ensure_ascii=False))

            # try up to 3 attempts with backoff
            max_attempts = 3
            last_text = None
            for attempt in range(1, max_attempts + 1):
                text = await self._call_llm_with_timeout(prompt, project_id, attempt=attempt)
                if not text:
                    backoff = min(2 ** attempt, 8)
                    logger.info("[SCHEDULE] LLM attempt %d failed, backoff %ds", attempt, backoff)
                    await asyncio.sleep(backoff)
                    continue

                last_text = text
                # try to extract first JSON block
                m = re.search(r"(\[[\s\S]*\])", text)
                if not m:
                    m = re.search(r"(\{[\s\S]*\})", text)
                    # if only object, try to wrap into array
                    if m:
                        candidate = m.group(1)
                        try:
                            parsed = json.loads(candidate)
                            # if object with id->duration, coerce into list
                            if isinstance(parsed, dict):
                                parsed = [parsed]
                            logger.info("[SCHEDULE] LLM returned JSON object parsed")
                            return parsed
                        except Exception:
                            pass
                    logger.warning("[SCHEDULE] LLM response contains no JSON array/object (attempt %d). Saving raw for debug.", attempt)
                    # try next attempt with backoff
                    backoff = min(2 ** attempt, 8)
                    await asyncio.sleep(backoff)
                    continue

                json_text = m.group(1)
                try:
                    parsed_arr = json.loads(json_text)
                    if isinstance(parsed_arr, list):
                        logger.info("[SCHEDULE] Parsed duration list from LLM (len=%d)", len(parsed_arr))
                        return parsed_arr
                except Exception as e:
                    logger.warning("[SCHEDULE] JSON parse error from LLM: %s", e)
                    # save last_text already done in _call_llm_with_timeout, try next attempt
                    backoff = min(2 ** attempt, 8)
                    await asyncio.sleep(backoff)
                    continue

            logger.warning("[SCHEDULE] LLM duration estimation failed after %d attempts", max_attempts)
            return []
        except Exception as e:
            logger.exception("[SCHEDULE] estimate_durations_via_llm unexpected error: %s", e)
            return []

    async def pipeline(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """요구사항, WBS, 변경이력을 종합해 RTM/WBS/변경관리표를 생성"""

        # existing normalization
        if not isinstance(payload, dict):
            if hasattr(payload, "model_dump"):
                payload = payload.model_dump()
            elif hasattr(payload, "dict"):
                payload = payload.dict()
            else:
                payload = {}

        project_id = payload.get("project_id", "Untitled")
        logger.info(f"[SCHEDULE] 📅 Schedule Pipeline 시작: {project_id}")
        
        methodology = (payload.get("methodology") or "waterfall").lower()
        sprint_length_weeks = int(payload.get("sprint_length_weeks") or 2)
        estimation_mode = payload.get("estimation_mode") or "heuristic"
        # 1111 개선
        wbs_src = payload.get("wbs_json")
        if not wbs_src:
            # ScopeAgent에서 생성한 요구사항 파일 자동 참조
            scope_req_path = Path(self.DATA_DIR) / "outputs" / "scope" / str(project_id) / "requirements.json"
            if scope_req_path.exists():
                try:
                    scope_json = json.loads(scope_req_path.read_text(encoding="utf-8"))
                    if "requirements" in scope_json:
                        # WBS 생성 프롬프트 호출
                        if self.llm:
                            from .prompts import WBS_SYNTH_PROMPT
                            req_str = json.dumps(scope_json["requirements"], ensure_ascii=False, indent=2)
                            prompt = WBS_SYNTH_PROMPT.format(requirements_json=req_str)
                            logger.info(f"[SCHEDULE] WBS 생성 LLM 호출 - 요구사항 {len(scope_json['requirements'])}개")
                            raw = await self._call_llm_with_timeout(prompt, project_id, attempt=1)
                            # JSON 파싱 시도
                            m = re.search(r"(\{[\s\S]*\})", raw or "")
                            if m:
                                try:
                                    wbs_src = json.loads(m.group(1))
                                    logger.info(f"[SCHEDULE] WBS JSON 파싱 성공 - {len(wbs_src.get('nodes', []))}개 노드")
                                except Exception as e:
                                    logger.warning(f"[SCHEDULE] WBS JSON 파싱 실패: {e}")
                        else:
                            logger.warning("[SCHEDULE] LLM 없음 → 요구사항 기반 WBS 생성 생략, 샘플 WBS 사용")
                except Exception as e:
                    logger.warning(f"[SCHEDULE] 요구사항 파일 로드 실패: {e}")

        change_requests = payload.get("change_requests")  # optional list

        wbs = await self._load_wbs(wbs_src)
        nodes = _flatten_wbs_nodes(wbs)

        # 1111 If estimation_mode == 'llm' and llm available, try LLM-based estimation first
        estimated = []
        if estimation_mode == "llm" and self.llm:
            logger.info("[SCHEDULE] estimation_mode=llm -> attempting LLM duration estimation")
            llm_result = await self._estimate_durations_via_llm(nodes, methodology, project_id)
            if llm_result and isinstance(llm_result, list):
                # Map LLM result to tasks list structure used downstream
                id_map = {n['id']: n for n in nodes}
                for item in llm_result:
                    tid = str(item.get("id"))
                    if tid not in id_map:
                        # skip unknown ids
                        logger.debug("[SCHEDULE] LLM returned unknown id: %s (skipped)", tid)
                        continue
                    dur = item.get("duration_days") or item.get("duration") or 1
                    preds = item.get("predecessors") or []
                    if isinstance(preds, str):
                        preds = [p.strip() for p in preds.split(",") if p.strip()]
                    estimated.append({"id": tid, "name": id_map[tid].get("name"), "duration": int(dur), "predecessors": preds})
                # if LLM produced nothing valid, fallback to heuristic
                if not estimated:
                    logger.warning("[SCHEDULE] LLM produced no valid estimated tasks -> falling back to heuristic")
                    estimated = _default_duration_estimator(nodes, methodology=methodology, sprint_length_weeks=sprint_length_weeks)
            else:
                logger.warning("[SCHEDULE] LLM estimation failed/empty -> fallback to heuristic")
                estimated = _default_duration_estimator(nodes, methodology=methodology, sprint_length_weeks=sprint_length_weeks)
        else:
            # default heuristic
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

        # rest of original pipeline remains the same (burndown, pmp outputs, change requests...)
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
# ---- end replacement block ----

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


# ---------------------------------------------------------------------
# PMP 표준 산출물 생성 (RTM, WBS, 변경관리)
# ---------------------------------------------------------------------
from server.workflow.agents.scope_agent.outputs.rtm_excel import RTMExcelGenerator
from server.workflow.agents.scope_agent.outputs.wbs_excel import WBSExcelGenerator
from server.workflow.agents.schedule_agent.outputs.change_mgmt import ChangeManagementGenerator

try:
    proj_dir = self.OUT_DIR / str(project_id)
    req_path = Path(self.DATA_DIR) / "outputs" / "scope" / str(project_id) / "requirements.json"
    wbs_path = proj_dir / "wbs_structure.json"

    # --- 요구사항 추적표 생성 ---
    if req_path.exists():
        req_json = json.loads(req_path.read_text(encoding="utf-8"))
        reqs = req_json.get("requirements", [])
        rtm_path = proj_dir / f"{project_id}_요구사항추적표.xlsx"
        RTMExcelGenerator.generate(requirements=reqs, output_path=rtm_path)
        logger.info(f"[SCHEDULE] ✅ RTM Excel 생성 완료: {rtm_path}")
    else:
        logger.warning("[SCHEDULE] requirements.json 없음 → RTM 건너뜀")

    # --- WBS Excel 생성 ---
    if wbs_path.exists():
        wbs_data = json.loads(wbs_path.read_text(encoding="utf-8"))
        
        # WBS / RTM 갱신 시 기존 파일이 있을 경우 append 로직 추가
        if wbs_excel_path.exists():
            logger.info(f"[SCHEDULE] 기존 WBS.xlsx 발견 - 업데이트 모드")
            # 기존 내용 로드 → 새 tasks merge
            existing = openpyxl.load_workbook(wbs_excel_path)
            ws = existing.active
            ws.append(["--- 업데이트 ---"])
            for t in rows_out:
                ws.append([t["id"], t["name"], t["duration"], t["start"], t["end"]])
            existing.save(wbs_excel_path)
        else: 
            # WBS 파일이 없을 경우 신규생성
            wbs_excel_path = proj_dir / f"{project_id}_WBS.xlsx"
            WBSExcelGenerator.generate(wbs_data=wbs_data, output_path=wbs_excel_path)
            logger.info(f"[SCHEDULE] ✅ WBS Excel 생성 완료: {wbs_excel_path}")

    else:
        logger.warning("[SCHEDULE] wbs_structure.json 없음 → WBS 건너뜀")

    # --- 변경관리표 생성 ---
    change_mgmt_path = proj_dir / f"{project_id}_변경관리.xlsx"
    ChangeManagementGenerator.generate(project_id=project_id, output_path=change_mgmt_path)
    logger.info(f"[SCHEDULE] ✅ 변경관리표 생성 완료: {change_mgmt_path}")



except Exception as e:
    logger.error(f"[SCHEDULE] ❌ outputs 생성 중 오류: {e}")
