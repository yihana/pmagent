"""
Scope Agent Prompts - 템플릿 / 룰 / Few-shot / RAG 통합 버전
"""
from pathlib import Path
import logging

logger = logging.getLogger("scope.prompts")

# ---------------------------------------------------------------------
# 프로젝트 루트 탐색
# ---------------------------------------------------------------------
def get_project_root() -> Path:
    cur = Path(__file__).resolve()
    for _ in range(10):
        cur = cur.parent
        if (cur / "templates").exists():
            return cur
    return Path.cwd()

PROJECT_ROOT = get_project_root()
TEMPLATE_DIR = PROJECT_ROOT / "templates"
RULES_DIR = PROJECT_ROOT / "rules"

# ---------------------------------------------------------------------
# 로더 함수들
# ---------------------------------------------------------------------
def _read_text(p: Path, fallback=""):
    try:
        return p.read_text(encoding="utf-8")
    except Exception as e:
        logger.warning(f"[PROMPTS] 로드 실패 {p}: {e}")
        return fallback

def load_template(name, fallback=""):
    return _read_text(TEMPLATE_DIR / name, fallback)

def load_rule(name, fallback=""):
    return _read_text(RULES_DIR / name, fallback)

def load_fewshot_examples() -> str:
    fewshot_dir = TEMPLATE_DIR / "fewshot"
    buf = []
    for f in fewshot_dir.glob("*.txt"):
        try:
            buf.append(f"\n\n### 🧩 {f.stem}\n" + f.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"[PROMPTS] few-shot 로드 실패 {f}: {e}")
    return "\n".join(buf)

# ---------------------------------------------------------------------
# 프롬프트 빌더
# ---------------------------------------------------------------------
def build_scope_prompt(context: str, mode="detailed", include_fewshot=True) -> str:
    base = load_template("scope_base.txt")
    schema = load_template("scope_schema.json")
    rules_text = load_rule("clarity.txt") + "\n" + load_rule("granularity.txt")
    fewshots = load_fewshot_examples() if include_fewshot else ""

    return f"""
{base}

## 📋 출력 JSON 구조
{schema}

{rules_text}

{fewshots}

## 📄 문서
{context[:8000]}

⚠️ JSON만 반환하세요.
"""

# ---------------------------------------------------------------------
# 하위 호환용 변수
# ---------------------------------------------------------------------
SCOPE_EXTRACT_PROMPT = "{context}"
RTM_PROMPT = "요구사항 추적표 생성용 간략 프롬프트"
WBS_SYNTHESIS_PROMPT = "WBS 생성은 Schedule Agent 역할 입니다."


# =============================================================================
# Project Charter 생성 프롬프트
# =============================================================================
PROJECT_CHARTER_PROMPT = """
당신은 PMP 표준을 준수하는 PMO 전문가입니다.
다음 요구사항 정의서를 바탕으로 **프로젝트 헌장(Project Charter)** 을 작성하세요.

## 입력 정보
- **프로젝트명**: {project_name}
- **스폰서**: {sponsor}
- **배경**: {background}
- **목표**: {objectives}

## 상위 수준 요구사항 (요약)
{requirements_summary}

요구사항의 우선순위, 기능·비기능 비율을 고려하여
프로젝트 목적, 범위, 주요 산출물, 리스크, 예산, 일정 등을 작성합니다.

⚠️ 순수 Markdown 형식으로 작성하세요. 표는 Markdown 표로 표현하세요.

(이하 Charter 본문 동일)
"""

# =============================================================================
# Tailoring 가이드 프롬프트
# =============================================================================
TAILORING_PROMPT = """
프로젝트 요구사항 정의서 기반으로 PMP 프로세스를 Tailoring하세요.

## 요구사항 통계
- 총 요구사항 수: {req_count}
- 기능 요구사항: {func_count}
- 비기능 요구사항: {nonfunc_count}
- 제약사항: {constraint_count}

## 프로젝트 특성
- **규모**: {size}
- **방법론**: {methodology}
- **복잡도**: {complexity}
- **팀 크기**: {team_size}명
- **기간**: {duration}개월

(이하 기존 본문 동일)
"""

