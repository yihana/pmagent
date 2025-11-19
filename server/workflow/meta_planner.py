# server/workflow/meta_planner.py

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from server.workflow.agents.scope_agent.pipeline import ScopeAgent
from server.workflow.agents.cost_agent.cost_agent import CostAgent
from server.workflow.agents.schedule_agent.pipeline import ScheduleAgent

# Optional: PM_Integrator, RiskAgent, QualityAgent
try:
    from server.workflow.agents.pm_integrator.integrator import PM_Integrator
except Exception:
    PM_Integrator = None

try:
    from server.workflow.agents.risk_agent.risk_agent import RiskAgent
except Exception:
    RiskAgent = None

try:
    from server.workflow.agents.quality_agent import QualityAgent
except Exception:
    QualityAgent = None

logger = logging.getLogger(__name__)


# ---------------- Planner structures ----------------

@dataclass
class PlannerStep:
    id: str
    agent: str                  # "scope" | "cost" | "schedule" | "risk" | "integrator"
    deps: List[str] = field(default_factory=list)
    enabled: bool = True
    config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PlannerPlan:
    project_id: str
    steps: List[PlannerStep]


# ---------------- Meta-Planner ----------------

class MetaPlanner:
    """
    ReWOO-style Meta-Planner (Planner–Worker–Solver)

    Planner:
      - payload 분석 → Plan(Graph) 생성

    Worker:
      - Scope → (Quality Check) → Cost → Schedule → (Risk) → (Integrator)

    Solver:
      - Proposal Manifest로 통합 후 파일 저장
    """

    def __init__(
        self,
        data_dir: str = "data",
        use_integrator: bool = False,
        use_risk: bool = True,
        use_quality: bool = False,
    ):
        self.data_dir = Path(data_dir)
        self.scope_agent = ScopeAgent()
        self.cost_agent = CostAgent()
        self.schedule_agent = ScheduleAgent()
        self.use_integrator = use_integrator

        self.risk_agent = RiskAgent() if (use_risk and RiskAgent is not None) else None
        self.quality_agent = QualityAgent() if (use_quality and QualityAgent is not None) else None

        logger.info(
            "[MetaPlanner] initialized (integrator=%s, risk=%s, quality=%s)",
            self.use_integrator, bool(self.risk_agent), bool(self.quality_agent)
        )

    # ---------------- Planner Phase ----------------

    def build_plan(self, payload: Dict[str, Any]) -> PlannerPlan:
        project_id = str(
            payload.get("project_id")
            or payload.get("project_name")
            or "unknown_project"
        )

        scope_cfg = payload.get("scope_options", {}) or {}
        sched_cfg = payload.get("schedule_options", {}) or {}

        steps: List[PlannerStep] = [
            PlannerStep(
                id="scope",
                agent="scope",
                deps=[],
                config=scope_cfg,
            ),
            PlannerStep(
                id="cost",
                agent="cost",
                deps=["scope"],
            ),
            PlannerStep(
                id="schedule",
                agent="schedule",
                deps=["scope"],
                config=sched_cfg,
            ),
        ]

        if self.risk_agent is not None:
            steps.append(
                PlannerStep(
                    id="risk",
                    agent="risk",
                    deps=["scope", "cost", "schedule"],
                )
            )

        if self.use_integrator and PM_Integrator is not None:
            steps.append(
                PlannerStep(
                    id="integrator",
                    agent="integrator",
                    deps=["scope", "cost", "schedule"],
                )
            )

        logger.info("[MetaPlanner] Plan 생성: %s", [s.id for s in steps])
        return PlannerPlan(project_id=project_id, steps=steps)

    # ---------------- Worker Phase ----------------

    async def run_scope(
        self,
        project_id: str,
        payload: Dict[str, Any],
        config: Dict[str, Any],
    ) -> Dict[str, Any]:
        rfp_text = (payload.get("rfp_text") or "").strip()
        documents = payload.get("documents") or []

        if not rfp_text and documents:
            first = documents[0]
            path = first.get("path") if isinstance(first, dict) else getattr(first, "path", None)
            if path and Path(path).exists():
                rfp_text = Path(path).read_text(encoding="utf-8", errors="ignore")

        options = dict(config or {})
        options.setdefault("methodology", payload.get("methodology", "waterfall"))

        scope_payload = {
            "project_id": project_id,
            "project_name": payload.get("project_name", project_id),
            "text": rfp_text,
            "documents": documents,
            "methodology": payload.get("methodology", "waterfall"),
            "options": options,
        }

        logger.info("[MetaPlanner] ▶ ScopeAgent 실행")
        scope_result = await self.scope_agent.pipeline(scope_payload)
        logger.info("[MetaPlanner] ◀ ScopeAgent 완료: %d reqs", len(scope_result.get("requirements", [])))

        # --- QualityAgent (옵션) ---
        if self.quality_agent is not None and options.get("run_quality_check"):
            try:
                logger.info("[MetaPlanner] ▶ QualityAgent 품질 검증 실행")
                qres = self.quality_agent.validate(
                    scope_result.get("requirements", []),
                    rfp_text,
                    metadata={"project_id": project_id},
                )
                scope_result["quality"] = qres
                logger.info(
                    "[MetaPlanner] ◀ QualityAgent 완료: score=%.1f, pass=%s",
                    qres.get("score", 0.0),
                    qres.get("pass"),
                )
            except Exception as e:
                logger.exception("[MetaPlanner] QualityAgent 실행 실패: %s", e)

        return scope_result

    def run_cost(self, scope_result: Dict[str, Any]) -> Dict[str, Any]:
        reqs = scope_result.get("requirements") or []
        logger.info("[MetaPlanner] ▶ CostAgent 실행")
        result = self.cost_agent.estimate_cost(reqs)
        logger.info("[MetaPlanner] ◀ CostAgent 완료")
        return result

    def run_schedule(
        self,
        project_id: str,
        payload: Dict[str, Any],
        config: Dict[str, Any],
    ) -> Dict[str, Any]:
        base_dir = self.data_dir / project_id
        req_json = base_dir / "requirements.json"
        wbs_json = base_dir / "wbs_structure.json"

        sched_payload = {
            "project_id": project_id,
            "methodology": payload.get("methodology", "waterfall"),
            "requirements_json": str(req_json),
            "wbs_json": str(wbs_json),
            "calendar": {
                "start_date": config.get("start_date")
                or datetime.now().date().isoformat()
            },
            "sprint_length_weeks": int(config.get("sprint_length_weeks", 2)),
            "estimation_mode": config.get("estimation_mode", "heuristic"),
            "use_got": bool(config.get("use_got", False)),
        }

        logger.info("[MetaPlanner] ▶ ScheduleAgent 실행")
        result = self.schedule_agent.create_schedule_from_payload(sched_payload)
        logger.info("[MetaPlanner] ◀ ScheduleAgent 완료 (status=%s)", result.get("status"))
        return result

    def run_risk(
        self,
        project_id: str,
        scope: Dict[str, Any],
        cost: Dict[str, Any],
        schedule: Dict[str, Any],
        actions: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        if self.risk_agent is None:
            return {"status": "skipped", "reason": "RiskAgent not available"}
        logger.info("[MetaPlanner] ▶ RiskAgent 실행")
        result = self.risk_agent.analyze(project_id, scope, cost, schedule, actions=actions)
        logger.info("[MetaPlanner] ◀ RiskAgent 완료")
        return result

    def run_integrator(
        self,
        scope: Dict[str, Any],
        cost: Dict[str, Any],
        schedule: Dict[str, Any],
        db_session=None,
    ) -> Dict[str, Any]:
        if PM_Integrator is None:
            return {"status": "skipped", "reason": "PM_Integrator unavailable"}
        if db_session is None:
            return {"status": "skipped", "reason": "db_session missing"}

        logger.info("[MetaPlanner] ▶ PM_Integrator 실행")
        integrator = PM_Integrator(db_session)
        snapshot = integrator.get_weekly_status(scope.get("project_id") or 0)
        logger.info("[MetaPlanner] ◀ PM_Integrator 완료")

        return {
            "status": "ok",
            "snapshot": snapshot,
        }

    # ---------------- Solver Phase ----------------

    def solve(
        self,
        project_id: str,
        scope_result: Dict[str, Any],
        cost_result: Dict[str, Any],
        schedule_result: Dict[str, Any],
        risk_result: Optional[Dict[str, Any]] = None,
        integrator_result: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        manifest: Dict[str, Any] = {
            "project_id": project_id,
            "generated_at": datetime.now().isoformat(),
            "scope": scope_result,
            "cost": cost_result,
            "schedule": schedule_result,
        }
        if risk_result is not None:
            manifest["risk"] = risk_result
        if integrator_result is not None:
            manifest["integrator"] = integrator_result

        out_dir = self.data_dir / project_id
        out_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = out_dir / "proposal_manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info("[MetaPlanner] Manifest 저장 완료: %s", manifest_path)
        return manifest

    # ---------------- High-level entry ----------------

    async def generate(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        logger.info("[MetaPlanner] 시작")
        project_id = str(
            payload.get("project_id")
            or payload.get("project_name")
            or "unknown_project"
        )

        plan = self.build_plan(payload)

        # 순서를 명시적으로 사용 (scope, cost, schedule, risk, integrator)
        scope_result = await self.run_scope(project_id, payload, plan.steps[0].config)
        cost_result = self.run_cost(scope_result)
        schedule_result = self.run_schedule(project_id, payload, plan.steps[2].config)

        risk_result = None
        if self.risk_agent is not None:
            risk_result = self.run_risk(project_id, scope_result, cost_result, schedule_result)

        integrator_result = None
        if self.use_integrator and PM_Integrator is not None:
            integrator_result = self.run_integrator(
                scope_result, cost_result, schedule_result,
                db_session=payload.get("db_session")
            )

        result = self.solve(
            project_id,
            scope_result,
            cost_result,
            schedule_result,
            risk_result,
            integrator_result,
        )

        logger.info("[MetaPlanner] 완료")
        return result
