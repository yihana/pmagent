# app/pages/pm_risk_agent.py

import json
from pathlib import Path

import streamlit as st

from server.workflow.agents.risk_agent.risk_agent import RiskAgent

st.set_page_config(page_title="Risk Agent", page_icon="⚠️")
st.title("⚠️ Risk Agent — 리스크 분석")

st.markdown(
    """
    Meta-Planner가 생성한 `proposal_manifest.json`을 기반으로
    Scope / Cost / Schedule 결과를 읽어와 RiskAgent로 리스크 요약을 계산합니다.
    """
)

project_id = st.text_input("프로젝트 ID", value="1010")

if st.button("리스크 분석 실행"):
    manifest_path = Path("data") / project_id / "proposal_manifest.json"

    if not manifest_path.exists():
        st.error(f"Manifest 파일이 없습니다: {manifest_path}")
    else:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        scope = manifest.get("scope", {})
        cost = manifest.get("cost", {})
        schedule = manifest.get("schedule", {})

        agent = RiskAgent()
        result = agent.analyze(project_id, scope, cost, schedule, actions=None)

        st.subheader("📌 프로젝트 리스크 요약")
        st.json(result.get("project_risks", {}))

        st.subheader("✅ 액션아이템 기반 리스크 (현재 actions=None이므로 비어있을 수 있음)")
        st.json(result.get("action_risks", {}))

        st.success("리스크 분석 완료")
