import os, json, datetime, csv
import networkx as nx
from langchain_openai import ChatOpenAI
from .prompts import DURATION_DEP_PROMPT
from server.core.logging import get_logger

log = get_logger("ScheduleAgent")

class ScheduleAgent:
    def __init__(self, model="gpt-4o-mini"):
        self.llm = ChatOpenAI(model=model, temperature=0)

    def estimate(self, wbs_json_path, methodology):
        wbs = json.load(open(wbs_json_path, encoding="utf-8"))
        prompt = DURATION_DEP_PROMPT.format(wbs_json=json.dumps(wbs["wbs"], ensure_ascii=False),
                                            methodology=methodology)
        plan = self.llm.invoke(prompt).content
        return json.loads(plan)

    def _add_days(self, start: datetime.date, days: int):
        return start + datetime.timedelta(days=days)

    def build_dag_and_schedule(self, estimates, calendar, sprint_weeks=None):
        G = nx.DiGraph()
        for t in estimates:
            G.add_node(t["id"], duration=int(t.get("duration_days",1)))
            for p in t.get("predecessors", []):
                G.add_edge(p, t["id"])

        critical_path = nx.dag_longest_path(G)

        start = datetime.date.fromisoformat(calendar["start_date"])
        topo = list(nx.topological_sort(G))
        start_dates, finish_dates = {}, {}

        for node in topo:
            preds = list(G.predecessors(node))
            es = start if not preds else max(finish_dates[p] for p in preds)
            dur = G.nodes[node]["duration"]
            fs = self._add_days(es, dur)
            start_dates[node], finish_dates[node] = es, fs

        rows = [['TaskID','Start','Finish']]
        for node in topo:
            rows.append([node, str(start_dates[node]), str(finish_dates[node])])

        os.makedirs('data/outputs/schedule/logs', exist_ok=True)
        with open('data/outputs/schedule/logs/execution.jsonl','a',encoding='utf-8') as f:
            f.write(json.dumps({'ts':datetime.datetime.utcnow().isoformat(), 'agent':'schedule','meta':{'critical_path':critical_path}}, ensure_ascii=False)+'\n')

        return rows, {'critical_path': critical_path}

    def write_outputs(self, rows, meta, outdir='data/outputs/schedule'):
        os.makedirs(outdir, exist_ok=True)
        with open(f"{outdir}/schedule_plan.csv","w",newline="",encoding="utf-8") as f:
            csv.writer(f).writerows(rows)
        json.dump({'critical_path': meta['critical_path']}, open(f"{outdir}/gantt.json","w",encoding="utf-8"), ensure_ascii=False, indent=2)
        return {
          'plan_csv': f"{outdir}/schedule_plan.csv",
          'gantt_json': f"{outdir}/gantt.json",
          'critical_path': meta['critical_path'],
          'weekly_reports_dir': f"{outdir}/reports"
        }
