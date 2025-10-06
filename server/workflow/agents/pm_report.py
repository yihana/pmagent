# server/workflow/pm_report.py
from datetime import date
from sqlalchemy.orm import Session
from typing import Tuple, Dict, Any
from server.db import pm_models

def build_weekly_md(db: Session, project_id: int, week_start: date, week_end: date) -> str:
    actions = db.query(pm_models.ActionItem)\
        .join(pm_models.Meeting).filter(pm_models.Meeting.project_id==project_id).all()
    risks = db.query(pm_models.Risk).filter(pm_models.Risk.project_id==project_id).all()

    done = [a for a in actions if a.status=="Done"]
    open_items = [a for a in actions if a.status!="Done"]

    md = []
    md.append(f"# Weekly Report (Project #{project_id})")
    md.append(f"- Period: {week_start} ~ {week_end}")
    md.append(f"- Action Items: total {len(actions)}, done {len(done)}, open {len(open_items)}")
    md.append("\n## Key Risks (Draft)")
    for r in risks[:5]:
        md.append(f"- **{r.title}** [{r.category}] P={r.probability} I={r.impact} → {r.priority_score}")
    md.append("\n## Next Week Plan (Auto-draft)")
    for a in open_items[:5]:
        md.append(f"- {a.task} (owner: {a.assignee or '-'}, due: {a.due_date or '-'})")
    return "\n".join(md)

def _evm_snapshot(db: Session, project_id: int, start: date, end: date) -> Dict[str, Any]:
    # 실제론 PV/EV/AC 계산 로직; 여기선 스텁
    return {"PV": 100, "EV": 95, "AC": 90, "SPI": 0.95, "CPI": 1.06}

def _roi_from_scenario(s: pm_models.PM_RoiScenario) -> Dict[str, Any]:
    hourly_rate = s.pm_monthly_rate / s.monthly_hours
    monthly = (s.analyzer_hours + s.reporter_hours + s.risk_hours) * hourly_rate
    period = monthly * s.months
    roi = (period / s.invest_cost * 100.0) if s.invest_cost > 0 else 0.0
    return {"monthly": monthly, "period": period, "roi": roi}

def build_weekly_md(db: Session, project_id: int, start: date, end: date) -> Tuple[str, Dict[str, Any]]:
    evm = _evm_snapshot(db, project_id, start, end)

    # ROI 개선 포인트(시나리오가 있으면 반영)
    roi_md = ""
    scen = db.query(pm_models.PM_RoiScenario).filter(pm_models.PM_RoiScenario.project_id==project_id).order_by(pm_models.PM_RoiScenario.id.desc()).first()
    if scen:
        r = _roi_from_scenario(scen)
        roi_md = f"""
### ROI 개선 포인트
- 월 절감액(만원): {r['monthly']:.1f}
- 기간 총 절감액(만원): {r['period']:.1f}
- ROI(%): {r['roi']:.1f}
(가정) 월단가 {scen.pm_monthly_rate}, 월근무 {scen.monthly_hours}h, 개월 {scen.months}, 투자비 {scen.invest_cost}
"""

    md = f"""# 주간보고 (PM Agent)
기간: {start} ~ {end}

## EVM 지표
- PV: {evm['PV']} / EV: {evm['EV']} / AC: {evm['AC']}
- SPI: {evm['SPI']} / CPI: {evm['CPI']}

{roi_md}
"""
    snap = {"evm": evm, "roi": roi_md}
    return md, snap    
