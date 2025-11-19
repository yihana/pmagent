from typing import List, Dict
# 간단 규칙 + 초안 등급 산정 (P/I High/Med/Low)
RBS = {
  "Schedule": ["지연","일정","테스트 환경","승인 대기","의존성"],
  "Scope": ["요구사항 변경","추가 요청","스코프"],
  "Cost": ["예산","비용","초과"],
  "Quality": ["결함","품질","버그"],
  "Resource": ["인력부족","담당자 부재","리소스"],
  "Communication": ["커뮤니케이션","전달 누락","오해"]
}

def classify_category(text: str) -> str:
    t = text
    for k, keys in RBS.items():
        if any(kw in t for kw in keys): return k
    return "Schedule"

def qualitative_score(category: str, text: str) -> tuple[str,str]:
    p = "Medium"; i = "Medium"
    if any(k in text for k in ["지연","승인 대기","의존성"]): p = "High"
    if any(k in text for k in ["결함","예산","초과"]): i = "High"
    return p, i

def draft_risks_from_actions(actions: List[Dict]) -> List[Dict]:
    risks=[]
    for it in actions[:5]:
        t = it.get("task","")
        cat = classify_category(t)
        p,i = qualitative_score(cat,t)
        risks.append({
          "title": t[:60],
          "category": cat,
          "cause": None,
          "event": None,
          "impact_area": ["Schedule"] if cat=="Schedule" else ["Scope"] if cat=="Scope" else ["Cost"] if cat=="Cost" else ["Quality"],
          "probability": p,
          "impact": i,
          "proximity": "Within 2 weeks" if "테스트" in t or "승인" in t else None,
          "detectability": "Medium",
          "urgency": "High" if p=="High" or i=="High" else "Medium",
          "controllability": "Medium",
          "priority_score": "H" if p=="High" and i=="High" else "M",
          "recommended_responses": ["사전 조율 미팅","의존성 분리","백업 플랜 수립"],
          "status": "Draft"
        })
    return risks
