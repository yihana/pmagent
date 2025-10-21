import os
import json
import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from server.db import pm_models
from server.db.database import get_db
from server.utils.config import get_llm

from server.workflow.agents.scope_agent.pipeline import ScopeAgent
from server.workflow.agents.schedule_agent.pipeline import ScheduleAgent

logger = logging.getLogger(__name__)


# ===============================
#  내부 유틸 함수
# ===============================
def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _json_dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)


# ===============================
#  메인 앱 클래스
# ===============================
class _App:
    def __init__(self, kind: str):
        self.kind = kind
        self.handler = {
            "analyze": self._analyze_handler,
            "scope_then_schedule": self._scope_then_schedule_handler,
        }.get(kind)

    async def ainvoke(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not self.handler:
            raise ValueError(f"Unknown pipeline kind: {self.kind}")
        return await self.handler(payload)

    # ==========================
    # 1️⃣ Analyzer (기존 기능)
    # ==========================
    async def _analyze_handler(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        db: Session = next(get_db())
        try:
            project_id = payload.get("project_id", 1001)
            title = payload.get("title", "PM 분석 문서")
            text = payload.get("text", "")
            doc_type = payload.get("doc_type", "meeting")

            # 문서 저장
            doc = pm_models.PM_Document(
                project_id=project_id,
                title=title,
                content=text,
                doc_type=doc_type,
                created_at=_utcnow(),
                uploaded_at=_utcnow(),
            )
            db.add(doc)
            db.flush()  # id 확보

            # ✅ meeting_id 자동 설정 (문서 id를 그대로 사용)
            meeting_id = doc.id

            # ScopeAgent + ScheduleAgent 로직 수행
            sa = ScopeAgent()
            sa.ingest([doc.title], chunk=500, overlap=100)
            items = sa.extract_items()
            wbs = sa.synthesize_wbs(items, "waterfall")
            scope_out = sa.write_outputs(items, wbs)

            sch = ScheduleAgent()
            est = sch.estimate(scope_out["wbs_json"], "waterfall")
            rows, meta = sch.build_dag_and_schedule(
                est,
                {"start_date": "2025-10-01", "end_date": "2025-12-31"},
                2,
            )
            sched_out = sch.write_outputs(rows, meta)

            # Action Items 저장
            saved = 0
            for item in items:
                item_dict = dict(item)
                ai = pm_models.PM_ActionItem(
                    project_id=project_id,
                    document_id=doc.id,
                    meeting_id=meeting_id,  # ✅ 자동 지정
                    title=item_dict.get("title") or item_dict.get("name"),
                    description=item_dict.get("description", ""),
                    owner=item_dict.get("owner", ""),
                    module=item_dict.get("module", ""),
                    phase=item_dict.get("phase", ""),
                    due=item_dict.get("due"),
                    priority=item_dict.get("priority", "Medium"),
                    created_at=_utcnow(),
                )
                db.add(ai)
                saved += 1

            db.commit()
            logger.info(
                f"[ANALYZE] Saved {saved} action items for project_id={project_id}, "
                f"document_id={doc.id}, meeting_id={meeting_id}"
            )

            return {
                "document": {"id": doc.id, "title": doc.title},
                "scope": scope_out,
                "schedule": sched_out,
                "action_items_saved": saved,
            }

        except SQLAlchemyError as e:
            db.rollback()
            logger.exception("[DB] SQLAlchemy error")
            raise RuntimeError(f"analyze failed (DB): {e}")
        except Exception as e:
            db.rollback()
            logger.exception("[ANALYZE] unexpected error")
            raise RuntimeError(f"analyze failed: {e}")
        finally:
            db.close()

    # ==========================
    # 2️⃣ Scope → Schedule 연동
    # ==========================
    async def _scope_then_schedule_handler(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        scope_in = payload.get("scope", {})
        schedule_in = payload.get("schedule", {})

        sa = ScopeAgent()
        sa.ingest(
            [d["path"] for d in scope_in.get("documents", [])],
            chunk=scope_in.get("options", {}).get("chunk_size", 500),
            overlap=scope_in.get("options", {}).get("overlap", 100),
        )
        items = sa.extract_items()
        wbs = sa.synthesize_wbs(items, scope_in.get("methodology", "waterfall"))
        scope_out = sa.write_outputs(items, wbs)

        sch = ScheduleAgent()
        est = sch.estimate(scope_out["wbs_json"], schedule_in.get("methodology", "waterfall"))
        rows, meta = sch.build_dag_and_schedule(
            est,
            schedule_in.get("calendar", {}),
            schedule_in.get("sprint_length_weeks"),
        )
        sched_out = sch.write_outputs(rows, meta)

        return {"scope": scope_out, "schedule": sched_out}


# ===============================
#  파이프라인 실행 진입점
# ===============================
async def run_pipeline(kind: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    app = _App(kind)
    return await app.ainvoke(payload)
