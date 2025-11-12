from __future__ import annotations
import os, re, json, asyncio, logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from server.utils.config import get_llm
from server.workflow.agents.schedule_agent.prompts import (
    RTM_PROMPT, WBS_ENRICH_PROMPT, CHANGE_MGMT_PROMPT
)

from server.workflow.agents.scope_agent.outputs.rtm_excel import RTMExcelGenerator
from server.workflow.agents.scope_agent.outputs.wbs_excel import WBSExcelGenerator
from server.workflow.agents.schedule_agent.outputs.change_mgmt import ChangeManagementGenerator

logger = logging.getLogger("schedule.agent")


# =============================================================================
# ScheduleAgent
# =============================================================================
class ScheduleAgent:
    def __init__(self, data_dir: str = "data/outputs/schedule"):
        self.llm = get_llm()
        self.DATA_DIR = Path(data_dir)
        self.OUT_DIR = self.DATA_DIR
        self.OUT_DIR.mkdir(parents=True, exist_ok=True)

    # -------------------------------------------------------------------------
    async def pipeline(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        요구사항, WBS, 변경이력을 종합해 RTM/WBS/변경관리(CPM) 표를 생성
        """
        # --- 기본 메타 ---
        project_id = payload.get("project_id", "Untitled")
        logger.info(f"[SCHEDULE] 📅 Schedule Pipeline 시작: {project_id}")

        # 디렉토리 준비
        scope_dir = Path("data/outputs/scope") / project_id
        sched_dir = self.OUT_DIR / project_id
        sched_dir.mkdir(parents=True, exist_ok=True)

        req_src = payload.get("requirements_json")
        wbs_src = payload.get("wbs_json")
        req_path = Path(req_src) if req_src and os.path.exists(req_src) else scope_dir / "requirements.json"
        wbs_path = Path(wbs_src) if wbs_src and os.path.exists(wbs_src) else scope_dir / "wbs_structure.json"

        if not req_path.exists():
            logger.warning(f"[SCHEDULE] requirements.json 없음: {req_path}")
        if not wbs_path.exists():
            logger.warning(f"[SCHEDULE] wbs_structure.json 없음: {wbs_path}")

        change_log_path = Path("data/history/change_log.json")

        results = {"project_id": project_id, "outputs": {}}

        # ------------------------------------------------------------------
        # 1️⃣ 요구사항 추적표 (RTM)
        # ------------------------------------------------------------------
        if req_path.exists():
            try:
                req_json = json.loads(req_path.read_text(encoding="utf-8"))
                reqs = req_json.get("requirements", [])
                req_str = json.dumps(reqs[:20], ensure_ascii=False, indent=2)
                prompt = RTM_PROMPT.format(requirements_json=req_str)

                logger.info(f"[SCHEDULE] 🤖 RTM 생성 프롬프트 호출")
                resp = await asyncio.to_thread(
                    self.llm.invoke,
                    [{"role": "user", "content": prompt}],
                )
                raw = self._safe_extract_raw(resp)
                try:
                    match = re.search(r"(\{[\s\S]*\})", raw)
                    _ = json.loads(match.group(1)) if match else {}
                except Exception:
                    logger.warning("[SCHEDULE] RTM JSON 파싱 실패, 엑셀만 생성")
                # 엑셀 생성
                rtm_path = sched_dir / f"{project_id}_요구사항추적표.xlsx"
                RTMExcelGenerator.generate(requirements=reqs, output_path=rtm_path)
                results["outputs"]["rtm_excel"] = str(rtm_path)
                logger.info(f"[SCHEDULE] ✅ RTM 생성 완료: {rtm_path}")
            except Exception as e:
                logger.error(f"[SCHEDULE] RTM 처리 중 오류: {e}")
        else:
            logger.warning("[SCHEDULE] requirements.json 없음 → RTM 건너뜀")

        # ------------------------------------------------------------------
        # 2️⃣ WBS 보완 및 일정 계산
        # ------------------------------------------------------------------
        if wbs_path.exists():
            wbs_json = json.loads(wbs_path.read_text(encoding="utf-8"))
            prompt = WBS_ENRICH_PROMPT.format(
                wbs_json=json.dumps(wbs_json, ensure_ascii=False, indent=2)
            )
            logger.info(f"[SCHEDULE] 🤖 WBS 일정보완 프롬프트 호출")
            try:
                resp = await asyncio.to_thread(
                    self.llm.invoke,
                    [{"role": "user", "content": prompt}],
                )
                raw = self._safe_extract_raw(resp)
                match = re.search(r"(\{[\s\S]*\})", raw)
                wbs_enriched = json.loads(match.group(1)) if match else wbs_json
            except Exception as e:
                logger.warning(f"[SCHEDULE] WBS 보완 실패: {e}")
                wbs_enriched = wbs_json

            # WBS 엑셀 저장
            wbs_excel_path = sched_dir / f"{project_id}_WBS.xlsx"
            WBSExcelGenerator.generate(wbs_data=wbs_enriched, output_path=wbs_excel_path)
            results["outputs"]["wbs_excel"] = str(wbs_excel_path)
            logger.info(f"[SCHEDULE] ✅ WBS Excel 생성 완료: {wbs_excel_path}")
        else:
            logger.warning("[SCHEDULE] wbs_structure.json 없음 → WBS 건너뜀")
            wbs_enriched = {"nodes": []}

        # ------------------------------------------------------------------
        # 3️⃣ CPM 계산 + 변경관리표 통합
        # ------------------------------------------------------------------
        logger.info(f"[SCHEDULE] ⚙️ CPM 계산 및 변경관리 시작")

        # 변경 요청 로드
        change_requests = []
        if change_log_path.exists():
            try:
                change_requests = json.loads(change_log_path.read_text(encoding="utf-8"))
            except Exception:
                logger.warning("[SCHEDULE] 변경로그 JSON 파싱 실패")

        # LLM 기반 변경요약 (선택)
        try:
            change_prompt = CHANGE_MGMT_PROMPT.format(
                change_requests=json.dumps(change_requests, ensure_ascii=False, indent=2)
            )
            _ = await asyncio.to_thread(
                self.llm.invoke,
                [{"role": "user", "content": change_prompt}],
            )
        except Exception as e:
            logger.warning(f"[SCHEDULE] 변경요약 LLM 호출 실패: {e}")

        # CPM + 변경관리 통합 실행
        change_excel_path = sched_dir / f"{project_id}_변경관리.xlsx"
        cm_out = ChangeManagementGenerator.generate(
            project_id=project_id,
            output_path=change_excel_path,
            wbs_data=wbs_enriched, # 시각화(HTML/PNG)
            changes=change_requests,
        )

        results["outputs"]["change_mgmt_excel"] = cm_out["excel"]
        results["outputs"]["critical_path_png"] = cm_out.get("critical_path_png")
        results["outputs"]["critical_path_html"] = cm_out.get("critical_path_html")   # 1112 ★ 추가
        results["outputs"]["critical_path"] = cm_out.get("critical_path")
        results["outputs"]["project_duration_days"] = cm_out.get("project_duration_days")

        logger.info(f"[SCHEDULE] ✅ CPM 계산 완료: Critical Path={cm_out.get('critical_path')}")

        # ------------------------------------------------------------------
        # 4️⃣ 최종 manifest 기록
        # ------------------------------------------------------------------
        schedule_manifest = {
            "project_id": project_id,
            "generated_at": datetime.now().isoformat(),
            "inputs": {
                "requirements": str(req_path) if req_path.exists() else None,
                "wbs_structure": str(wbs_path) if wbs_path.exists() else None,
            },
            "outputs": results["outputs"],
            "cpm": {
                "duration_days": cm_out.get("project_duration_days"),
                "critical_path": cm_out.get("critical_path", []),
                "html": results["outputs"].get("critical_path_html"),
                "png": results["outputs"].get("critical_path_png"),
            },
        }

        manifest_path = sched_dir / "schedule_manifest.json"
        manifest_path.write_text(
            json.dumps(schedule_manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        results["manifest"] = str(manifest_path)

        # === Proposal manifest 갱신 (Scope + Schedule 연결) ===
        proposal_dir = Path("data/outputs/proposal") / str(project_id)
        proposal_dir.mkdir(parents=True, exist_ok=True)
        proposal_manifest_path = proposal_dir / "manifest.json"

        base = {
            "project_id": project_id,
            "scope": {},
            "schedule": {},
            "generated_at": datetime.now().isoformat(),
        }
        if proposal_manifest_path.exists():
            try:
                base = json.loads(proposal_manifest_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        base["schedule"] = schedule_manifest

        proposal_manifest_path.write_text(
            json.dumps(base, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        logger.info(f"[SCHEDULE] 📦 proposal manifest 갱신 완료: {proposal_manifest_path}")
        logger.info(f"[SCHEDULE] 📦 전체 산출물 및 CPM 저장 완료: {manifest_path}")
        return results

    # ----------------------------------------------------------------------
    def _safe_extract_raw(self, resp: Any) -> str:
        """LLM 응답에서 텍스트 안전 추출"""
        try:
            if isinstance(resp, str):
                return resp
            if hasattr(resp, "content"):
                return str(resp.content)
            if hasattr(resp, "choices"):
                return resp.choices[0].message.get("content", "")
            if hasattr(resp, "generations"):
                gens = getattr(resp, "generations")
                if isinstance(gens, list) and gens and hasattr(gens[0], "message"):
                    return gens[0].message.content
            return str(resp)
        except Exception as e:
            logger.warning(f"[SCHEDULE] raw extract 실패: {e}")
            return str(resp)
