# server/workflow/agents/scope_agent/output/
class ProjectPlanGenerator:
    @staticmethod
    def generate(project_name, requirements, wbs_data, options=None, output_path=None):
        import json
        import logging
        from pathlib import Path
        logger = logging.getLogger("scope.agent")

        # 기본 더미 출력
        out_path = Path(output_path or f"data/{project_name}_사업수행계획서_dummy.xlsx")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps({
            "project_name": project_name,
            "requirements": len(requirements),
            "wbs_nodes": len(wbs_data.get("nodes", [])),
            "options": options or {}
        }, ensure_ascii=False, indent=2), encoding="utf-8")

        logger.info(f"[SCOPE] (임시) ProjectPlanGenerator.generate() → {out_path}")
        return str(out_path)
