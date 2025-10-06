# server/workflow/pm_graph.py
from __future__ import annotations
from typing import Dict, Any
from datetime import date
from langgraph.graph import StateGraph, END

from server.workflow.state import PMState
from server.workflow.agents.pm_analyzer import PM_AnalyzerAgent
from server.workflow.agents.pm_risk import draft_risks_from_actions   # 함수형 가정
from server.workflow.agents.pm_report import build_weekly_md          # (md, snap) 반환
from server.db import pm_models, pm_crud

# --- 노드 구현 ---------------------------------------------------------

def make_analyzer_node(model_name: str = "gpt-4o", temperature: float = 0.2):
    analyzer = PM_AnalyzerAgent(model_name=model_name, temperature=temperature)

    async def node(state: PMState) -> PMState:
        db = state.get("db")
        project_id = state["project_id"]
        doc_type = state.get("doc_type", "meeting")
        title = state.get("title", f"{doc_type}")
        text = state.get("text", "")

        # 1) 문서 인제스트 (DB 저장)
        doc = pm_models.PMDocument(
            project_id=project_id,
            doc_type=doc_type,
            title=title,
            content=text,
            meta={}
        )
        db.add(doc); db.commit(); db.refresh(doc)

        # 2) 분석 호출
        if doc_type == "meeting":
            items = analyzer.analyze_minutes(text, project_meta={"project_id": project_id})
        elif doc_type == "rfp":
            items = analyzer.analyze_rfp(text, project_meta={"project_id": project_id})
        elif doc_type == "proposal":
            items = analyzer.analyze_proposal(text, project_meta={"project_id": project_id})
        elif doc_type == "issue":
            items = analyzer.analyze_issue(text, project_meta={"project_id": project_id})
        else:
            items = analyzer.analyze_minutes(text, project_meta={"project_id": project_id})

        # 3) 액션아이템 저장
        for it in items:
            ai = pm_models.PMActionItem(
                project_id=project_id, document_id=doc.id,
                assignee=it.get("assignee"),
                task=it.get("task","").strip(),
                due_date=it.get("due_date"),
                priority=it.get("priority","Medium"),
                status=it.get("status","Open"),
                module=it.get("module"),
                phase=it.get("phase"),
                evidence_span=it.get("evidence_span"),
                expected_effort=it.get("expected_effort"),
                expected_value=it.get("expected_value"),
            )
            db.add(ai)
        db.commit()

        return {
            "document_id": doc.id,
            "action_items": items,
        }
    return node


async def risk_node(state: PMState) -> PMState:
    """Analyzer가 만든 action_items를 바탕으로 라이트 리스크 태깅."""
    db = state.get("db")
    project_id = state["project_id"]

    acts = state.get("action_items")
    if not acts:
        # 최근 액션에서 가져오기 (백업 루트)
        acts_db = (
            db.query(pm_models.PMActionItem)
              .filter(pm_models.PMActionItem.project_id == project_id)
              .order_by(pm_models.PMActionItem.id.desc())
              .limit(100)
              .all()
        )
        acts = [{"task": a.task} for a in acts_db]
    else:
        acts = [{"task": a.get("task","")} for a in acts]

    risks = draft_risks_from_actions(acts)  # [{...}]
    # 저장(옵션): pm_crud.save_risks(db, project_id, risks, source_meeting_id=None)
    return {"risks": risks}


async def reporter_node(state: PMState) -> PMState:
    db = state["db"]
    project_id = state["project_id"]
    week_start = date.fromisoformat(state["week_start"])
    week_end = date.fromisoformat(state["week_end"])

    md, snap = build_weekly_md(db, project_id, week_start, week_end)

    # 저장 (파일/DB) — 필요시 pm_crud 사용
    pm_crud.save_weekly_report(
        db, project_id, week_start, week_end, summary_md=md, snap=snap, file_path=None
    )
    return {"report_md": md, "snapshot": snap}

# --- 그래프 조립 -------------------------------------------------------

def create_pm_graph(mode: str, model_name: str = "gpt-4o", temperature: float = 0.2):
    """
    mode:
      - "analyze" : analyzer만
      - "risk"    : risk만 (최근 액션 기준)
      - "report"  : analyzer -> risk -> reporter
    """
    g = StateGraph(PMState)

    # 노드 등록
    g.add_node("ANALYZER", make_analyzer_node(model_name, temperature))
    g.add_node("RISK", risk_node)
    g.add_node("REPORTER", reporter_node)

    # 흐름 연결
    if mode == "analyze":
        g.set_entry_point("ANALYZER")
        g.add_edge("ANALYZER", END)

    elif mode == "risk":
        g.set_entry_point("RISK")
        g.add_edge("RISK", END)

    elif mode == "report":
        g.set_entry_point("ANALYZER")
        g.add_edge("ANALYZER", "RISK")
        g.add_edge("RISK", "REPORTER")
        g.add_edge("REPORTER", END)

    else:
        raise ValueError(f"Unknown mode: {mode}")

    return g.compile()

# --- 실행 헬퍼 ---------------------------------------------------------

async def run_pipeline(mode: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    payload 예:
    {
      "db": Session,
      "project_id": 1,
      "doc_type": "meeting",
      "title": "주간회의",
      "text": "회의록 본문...",
      "week_start": "2025-09-22",
      "week_end": "2025-09-28",
    }
    """
    app = create_pm_graph(mode)
    result = await app.ainvoke(payload)
    return result

# === [ADAPTER START] expose debate_graph to external import ====================
# 목적:
# - 외부에서 `from server.workflow.pm_graph import debate_graph`
#   또는 `get_debate_graph()/build_debate_graph()`로 안전하게 접근 가능하게 함
# - 프로젝트 내부에 이미 있는 빌더 함수명이 달라도 최대한 자동으로 찾아 사용
# - 전혀 없을 땐 디버그용 더미 그래프를 제공(스트리밍 파이프 검증용)

from typing import Any, Dict

_debate_graph_singleton = None  # 캐시

def _find_and_build_graph():
    """
    pm_graph 내에 존재할 법한 빌더를 자동 탐색해 생성합니다.
    우선순위:
      - 전역변수 debate_graph
      - get_debate_graph()
      - build_debate_graph()
      - create_debate_graph()
      - create_graph()
      - build_graph()
      - make_graph()
    없으면 디버그용 더미 그래프를 반환합니다.
    """
    # 1) 이미 전역에 만들어져 있으면 그대로 반환
    g = globals().get("debate_graph")
    if g is not None:
        return g

    # 2) 흔한 팩토리 이름들을 순서대로 탐색
    for name in [
        "get_debate_graph",
        "build_debate_graph",
        "create_debate_graph",
        "create_graph",
        "build_graph",
        "make_graph",
    ]:
        fn = globals().get(name)
        if callable(fn):
            try:
                return fn()
            except Exception:
                # 빌더가 있어도 내부 예외가 나면 다음 후보 시도
                pass

    # 3) 아무것도 없으면 더미 그래프(스트림 파이프/프론트 파서 검증용)
    class _DummyGraph:
        def stream(self, state: Dict[str, Any], stream_mode: str = "updates", config: Dict[str, Any] | None = None):
            text = "더미 그래프입니다. pm_graph에 debate_graph 빌더를 노출하세요."
            for ch in text.split():
                yield {"text": ch}

    return _DummyGraph()

def build_debate_graph():
    global _debate_graph_singleton
    if _debate_graph_singleton is None:
        _debate_graph_singleton = _find_and_build_graph()
    return _debate_graph_singleton

def get_debate_graph():
    # 별칭
    return build_debate_graph()

# import 시점에 곧바로 접근 가능한 전역 심볼도 제공
debate_graph = build_debate_graph()
# === [ADAPTER END] ============================================================
