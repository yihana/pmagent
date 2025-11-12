# check_and_create_templates.py
"""
기존 templates/rules 폴더 확인 및 누락 파일 자동 생성
"""

from pathlib import Path

# =============================================================================
# 프로젝트 루트 찾기
# =============================================================================

def find_project_root():
    """templates 폴더가 있는 프로젝트 루트 찾기"""
    current = Path.cwd()
    
    for _ in range(10):
        if (current / "templates").exists():
            return current
        current = current.parent
    
    return Path.cwd()


PROJECT_ROOT = find_project_root()
TEMPLATE_DIR = PROJECT_ROOT / "templates"
RULES_DIR = PROJECT_ROOT / "rules"

print(f"📁 프로젝트 루트: {PROJECT_ROOT}")
print(f"📁 템플릿 경로: {TEMPLATE_DIR}")
print(f"📁 규칙 경로: {RULES_DIR}")
print()


# =============================================================================
# 필요한 파일 정의
# =============================================================================

REQUIRED_FILES = {
    "templates/scope_base.txt": """당신은 PMP 표준을 준수하는 전문 PMO 분석가입니다.

## 🎯 임무
아래 문서에서 **구체적이고 실행 가능한** 요구사항을 추출하세요.

## ⚠️ 핵심 원칙

### 1. 독립성
각 요구사항은 독립적으로 구현 가능해야 함

### 2. 명확성
모호한 표현 제거: "빠르게" → "1초 이내"

### 3. 완전성
최소 10개 이상 추출 (작은 프로젝트는 5개)

## 📊 요구사항 유형

- **functional**: 시스템이 수행할 기능
- **non-functional**: 성능, 보안, 가용성  
- **constraint**: 제약사항 (예산, 일정)

## 🎯 우선순위

- **High**: 핵심 기능
- **Medium**: 중요하지만 단계적 구현
- **Low**: 부가 기능
""",

    "templates/scope_schema.json": """{
  "requirements": [
    {
      "req_id": "REQ-001",
      "title": "간결한 제목 (20자 이내)",
      "type": "functional",
      "priority": "High",
      "description": "상세 설명 (1-2문장)",
      "source_span": "문서 위치",
      "acceptance_criteria": [
        "검증 가능한 기준 1",
        "검증 가능한 기준 2"
      ]
    }
  ]
}
""",

    "templates/examples/functional.txt": """예시 1: Functional 요구사항

{
  "req_id": "REQ-001",
  "title": "이메일 기반 회원가입",
  "type": "functional",
  "priority": "High",
  "description": "사용자는 이메일과 비밀번호로 계정을 생성할 수 있어야 한다. 중복 이메일은 거부되며, 비밀번호는 8자 이상이어야 한다.",
  "source_span": "2.1 사용자 관리",
  "acceptance_criteria": [
    "이메일 형식 유효성 검증",
    "중복 이메일 가입 방지",
    "비밀번호 8자 이상, 영문+숫자+특수문자 포함"
  ]
}
""",

    "templates/examples/non_functional.txt": """예시: Non-functional 요구사항

{
  "req_id": "REQ-010",
  "title": "API 응답 시간",
  "type": "non-functional",
  "priority": "High",
  "description": "모든 API 엔드포인트는 평균 1초 이내에 응답해야 한다.",
  "source_span": "3.1 성능 요구사항",
  "acceptance_criteria": [
    "95 percentile 응답 시간 1.0초 이내",
    "동시 100명 사용자 부하 테스트 통과"
  ]
}
""",

    "rules/clarity.txt": """## 명확성 규칙

### 모호한 표현 제거

❌ "빠른 응답"    → ✅ "1초 이내 응답"
❌ "적절한 보안"  → ✅ "HTTPS + JWT 인증"
❌ "충분한 용량"  → ✅ "동시 1000명 지원"

### 측정 가능한 기준

모든 요구사항은 테스트 가능해야 합니다.
""",

    "rules/granularity.txt": """## 세분화 규칙

### 하나의 요구사항 = 하나의 기능

❌ 나쁜 예: "사용자 관리 (회원가입, 로그인, 프로필 포함)"

✅ 좋은 예:
- REQ-001: 이메일 회원가입
- REQ-002: 로그인 인증
- REQ-003: 프로필 수정
"""
}


# =============================================================================
# 파일 확인 및 생성
# =============================================================================

def check_and_create():
    """파일 확인 및 누락 파일 생성"""
    
    print("🔍 파일 확인 중...\n")
    
    existing = []
    missing = []
    created = []
    
    for rel_path, content in REQUIRED_FILES.items():
        full_path = PROJECT_ROOT / rel_path
        
        if full_path.exists():
            existing.append(rel_path)
            print(f"✅ 존재: {rel_path}")
        else:
            missing.append(rel_path)
            print(f"❌ 없음: {rel_path}")
    
    if not missing:
        print(f"\n🎉 모든 필수 파일이 존재합니다! ({len(existing)}개)")
        return
    
    print(f"\n⚠️ 누락된 파일: {len(missing)}개")
    
    # 사용자 확인
    response = input("\n누락된 파일을 생성하시겠습니까? (y/N): ").strip().lower()
    
    if response != 'y':
        print("취소되었습니다.")
        return
    
    print("\n📝 파일 생성 중...\n")
    
    for rel_path in missing:
        full_path = PROJECT_ROOT / rel_path
        content = REQUIRED_FILES[rel_path]
        
        try:
            # 디렉토리 생성
            full_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 파일 생성
            full_path.write_text(content.strip(), encoding='utf-8')
            
            created.append(rel_path)
            print(f"✅ 생성: {rel_path}")
            
        except Exception as e:
            print(f"❌ 실패: {rel_path} ({e})")
    
    print(f"\n🎉 완료! {len(created)}개 파일 생성")
    
    if created:
        print("\n생성된 파일:")
        for path in created:
            print(f"  - {path}")


# =============================================================================
# 기존 파일 목록 출력
# =============================================================================

def list_existing_files():
    """기존 파일 목록 출력"""
    
    print("\n" + "="*70)
    print("📂 기존 파일 목록")
    print("="*70)
    
    if TEMPLATE_DIR.exists():
        print(f"\n📁 {TEMPLATE_DIR}:")
        template_files = list(TEMPLATE_DIR.rglob("*.txt")) + list(TEMPLATE_DIR.rglob("*.json"))
        if template_files:
            for f in sorted(template_files):
                size = f.stat().st_size
                print(f"  ✓ {f.relative_to(TEMPLATE_DIR)} ({size} bytes)")
        else:
            print("  (비어있음)")
    else:
        print(f"\n❌ 템플릿 폴더 없음: {TEMPLATE_DIR}")
    
    if RULES_DIR.exists():
        print(f"\n📁 {RULES_DIR}:")
        rule_files = list(RULES_DIR.rglob("*.txt"))
        if rule_files:
            for f in sorted(rule_files):
                size = f.stat().st_size
                print(f"  ✓ {f.relative_to(RULES_DIR)} ({size} bytes)")
        else:
            print("  (비어있음)")
    else:
        print(f"\n❌ 규칙 폴더 없음: {RULES_DIR}")


# =============================================================================
# 메인
# =============================================================================

if __name__ == "__main__":
    print("="*70)
    print("📋 템플릿/규칙 파일 확인 도구")
    print("="*70)
    print()
    
    # 기존 파일 목록
    list_existing_files()
    
    print()
    
    # 필수 파일 확인 및 생성
    check_and_create()
    
    print()
    print("="*70)
    print("✅ 완료!")
    print("="*70)