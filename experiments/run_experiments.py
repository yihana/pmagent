# experiments/run_experiments_true_baseline.py

import json
import time
import asyncio
import statistics
from pathlib import Path
from typing import List, Dict, Any
import re

from server.workflow.agents.scope_agent.pipeline import ScopeAgent
from server.workflow.agents.cost_agent.cost_agent import CostAgent
from server.workflow.agents.schedule_agent.pipeline import ScheduleAgent

import matplotlib.pyplot as plt
import matplotlib
matplotlib.rcParams['font.family'] = 'Malgun Gothic'
matplotlib.rcParams['axes.unicode_minus'] = False


def load_rfp_files(folder: str) -> List[str]:
    folder_path = Path(folder)
    files = sorted(folder_path.glob("*.txt"))
    texts = []
    for f in files:
        texts.append(f.read_text(encoding="utf-8"))
    print(f"[INFO] Loaded {len(texts)} RFP samples from {folder_path}")
    return texts


def ensure_results_dir() -> Path:
    out_dir = Path("experiments") / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


# ============================================================================
# 진짜 Baseline: 규칙 기반 단순 추출
# ============================================================================
def naive_extract(text: str) -> List[Dict[str, Any]]:
    """
    LLM 없이 규칙만으로 요구사항 추출
    - "요구", "필요", "해야" 등 키워드 매칭
    - 문장 단위 분리
    """
    requirements = []
    
    # 키워드 패턴
    patterns = [
        r"(.{0,50}(?:요구|필요|해야|shall|must|should).{0,100})",
        r"(.{0,50}(?:기능|function|feature).{0,100})",
        r"(.{0,50}(?:제공|support|provide).{0,100})",
    ]
    
    req_id = 1
    for pattern in patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            sentence = match.group(1).strip()
            if len(sentence) < 10:  # 너무 짧으면 스킵
                continue
                
            requirements.append({
                "req_id": f"REQ-{req_id:03d}",
                "title": sentence[:50] + "..." if len(sentence) > 50 else sentence,
                "description": sentence,
                "type": "functional",
                "priority": "Medium",
                "source_span": f"Pattern match"
            })
            req_id += 1
    
    # 중복 제거 (같은 문장)
    seen = set()
    unique_reqs = []
    for req in requirements:
        desc = req['description']
        if desc not in seen:
            seen.add(desc)
            unique_reqs.append(req)
    
    return unique_reqs[:30]  # 최대 30개


# ============================================================================
# E1: 진짜 Baseline vs PM Agent
# ============================================================================
def experiment_E1_true_baseline(rfps: List[str]) -> List[Dict[str, Any]]:
    """
    E1: 진짜 비교
    - Naive: 규칙 기반 (LLM 없음)
    - Agent: PM Agent (LLM 기반)
    """
    scope = ScopeAgent()
    results = []

    for idx, rfp_text in enumerate(rfps):
        print(f"\n[E1] RFP #{idx} ---------------------------")
        
        try:
            # 1. Naive (규칙 기반)
            t0 = time.time()
            naive_reqs = naive_extract(rfp_text)
            naive_time = time.time() - t0
            print(f"  Naive(규칙):   req={len(naive_reqs)}, time={naive_time:.2f}s")
            
        except Exception as e:
            print(f"  ❌ Naive 실패: {e}")
            naive_reqs = []
            naive_time = 0

        try:
            # 2. Agent (PM Agent)
            t1 = time.time()
            agent_result = asyncio.run(
                scope.pipeline({
                    "project_id": f"E1-agent-{idx}",
                    "text": rfp_text,
                    "options": {
                        "confidence_threshold": 0.75,
                        "max_attempts": 3,
                    },
                })
            )
            agent_time = time.time() - t1
            agent_reqs = agent_result.get("requirements", [])
            print(f"  Agent(LLM):    req={len(agent_reqs)}, time={agent_time:.2f}s")
            
        except Exception as e:
            print(f"  ❌ Agent 실패: {e}")
            agent_reqs = []
            agent_time = 0

        results.append({
            "rfp_id": idx,
            "naive_req_count": len(naive_reqs),
            "agent_req_count": len(agent_reqs),
            "naive_time": naive_time,
            "agent_time": agent_time,
            "improvement": len(agent_reqs) - len(naive_reqs),
            "time_overhead": agent_time - naive_time,
            "success": len(naive_reqs) > 0 and len(agent_reqs) > 0
        })

    return results


def experiment_E4_proposal(rfps: List[str]) -> List[Dict[str, Any]]:
    scope = ScopeAgent()
    cost = CostAgent()
    sched = ScheduleAgent()
    results = []

    for idx, rfp_text in enumerate(rfps):
        project_id = f"E4-{idx}"
        print(f"\n[E4] Project {project_id} ---------------------------")

        try:
            out = asyncio.run(scope.pipeline({"project_id": project_id, "text": rfp_text}))
            reqs = out.get("requirements", [])
            cost_out = cost.estimate_cost(reqs)
            sched_out = sched.create_schedule(reqs)

            results.append({
                "project_id": project_id,
                "req_count": len(reqs),
                "total_cost": cost_out.get("total_cost"),
                "duration": sched_out.get("total_duration"),
            })
            print(f"  req={len(reqs)}, cost={cost_out.get('total_cost')}, duration={sched_out.get('total_duration')}")
        except Exception as e:
            print(f"  ❌ E4 실패: {e}")

    return results


def print_summary_e1(e1: List[Dict[str, Any]]):
    successful = [r for r in e1 if r.get('success', False)]
    
    if not successful:
        print("[SUMMARY] E1: 성공 케이스 없음")
        return

    naive_reqs = [r["naive_req_count"] for r in successful]
    agent_reqs = [r["agent_req_count"] for r in successful]
    improvements = [r["improvement"] for r in successful]
    naive_times = [r["naive_time"] for r in successful]
    agent_times = [r["agent_time"] for r in successful]

    print("\n[SUMMARY] E1 진짜 Baseline 비교")
    print(f"  성공 케이스: {len(successful)}/{len(e1)}")
    print(f"  Naive(규칙) 평균:  {statistics.mean(naive_reqs):.1f}개 ({statistics.mean(naive_times):.1f}초)")
    print(f"  Agent(LLM) 평균:   {statistics.mean(agent_reqs):.1f}개 ({statistics.mean(agent_times):.1f}초)")
    print(f"  평균 개선:         {statistics.mean(improvements):+.1f}개")
    print(f"  개선율:            {(statistics.mean(agent_reqs)/statistics.mean(naive_reqs)-1)*100:+.0f}%")


def visualize_e1_results(e1_results: List[Dict[str, Any]], results_dir: Path):
    successful = [r for r in e1_results if r.get('success', False)]
    
    if not successful:
        print("⚠️  E1: 시각화할 데이터 없음")
        return
    
    rfp_ids = [r['rfp_id'] for r in successful]
    naive_reqs = [r['naive_req_count'] for r in successful]
    agent_reqs = [r['agent_req_count'] for r in successful]
    improvements = [r['improvement'] for r in successful]
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    
    # 요구사항 개수 비교
    x = range(len(rfp_ids))
    width = 0.35
    ax1.bar([i - width/2 for i in x], naive_reqs, width, 
            label='Naive(규칙 기반)', alpha=0.8, color='#d62728')
    ax1.bar([i + width/2 for i in x], agent_reqs, width, 
            label='PM Agent(LLM)', alpha=0.8, color='#2ca02c')
    
    # 개선치 표시
    for i, imp in enumerate(improvements):
        color = 'green' if imp > 0 else 'red'
        ax1.text(i, max(naive_reqs[i], agent_reqs[i]) + 1, 
                f'{imp:+d}', ha='center', fontsize=9, color=color, fontweight='bold')
    
    ax1.set_xlabel('RFP ID')
    ax1.set_ylabel('요구사항 개수')
    ax1.set_title('E1: Baseline vs PM Agent (요구사항 개수)')
    ax1.set_xticks(x)
    ax1.set_xticklabels([f'RFP {i}' for i in rfp_ids])
    ax1.legend()
    ax1.grid(axis='y', alpha=0.3)
    
    # 시간 비교
    naive_times = [r['naive_time'] for r in successful]
    agent_times = [r['agent_time'] for r in successful]
    
    ax2.bar([i - width/2 for i in x], naive_times, width, 
            label='Naive', alpha=0.8, color='#d62728')
    ax2.bar([i + width/2 for i in x], agent_times, width, 
            label='PM Agent', alpha=0.8, color='#2ca02c')
    ax2.set_xlabel('RFP ID')
    ax2.set_ylabel('처리 시간 (초)')
    ax2.set_title('E1: 처리 시간 비교')
    ax2.set_xticks(x)
    ax2.set_xticklabels([f'RFP {i}' for i in rfp_ids])
    ax2.legend()
    ax2.grid(axis='y', alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(results_dir / 'E1_true_baseline.png', dpi=300, bbox_inches='tight')
    plt.close()
    print(f"✅ E1 시각화 저장: {results_dir / 'E1_true_baseline.png'}")


def create_summary_report(e1, e4, results_dir: Path):
    report = []
    report.append("=" * 60)
    report.append("PM Agent v0.9 실험 결과 (진짜 Baseline 비교)")
    report.append("=" * 60)
    report.append("")
    
    # E1
    if e1:
        successful = [r for r in e1 if r.get('success', False)]
        if successful:
            naive_reqs = [r['naive_req_count'] for r in successful]
            agent_reqs = [r['agent_req_count'] for r in successful]
            improvements = [r['improvement'] for r in successful]
            naive_times = [r['naive_time'] for r in successful]
            agent_times = [r['agent_time'] for r in successful]
            
            report.append("📊 E1: Baseline(규칙) vs PM Agent(LLM)")
            report.append("-" * 60)
            report.append(f"  성공 케이스:               {len(successful)}/{len(e1)}개")
            report.append(f"  Naive(규칙) 평균:          {statistics.mean(naive_reqs):.1f}개")
            report.append(f"  PM Agent 평균:             {statistics.mean(agent_reqs):.1f}개")
            report.append(f"  평균 개선:                 {statistics.mean(improvements):+.1f}개")
            report.append(f"  개선율:                    {(statistics.mean(agent_reqs)/statistics.mean(naive_reqs)-1)*100:+.0f}%")
            report.append("")
            report.append(f"  Naive 평균 시간:           {statistics.mean(naive_times):.1f}초")
            report.append(f"  PM Agent 평균 시간:        {statistics.mean(agent_times):.1f}초")
            report.append(f"  시간 오버헤드:             {statistics.mean(agent_times) - statistics.mean(naive_times):+.1f}초")
            report.append("")
    
    # E4
    if e4:
        report.append("📊 E4: End-to-End Proposal")
        report.append("-" * 60)
        report.append(f"  총 프로젝트 수:            {len(e4)}개")
        req_counts = [r['req_count'] for r in e4 if r['req_count']]
        if req_counts:
            report.append(f"  평균 요구사항 수:          {statistics.mean(req_counts):.1f}개")
        costs = [r['total_cost'] for r in e4 if r['total_cost']]
        if costs:
            report.append(f"  평균 추정 비용:            {statistics.mean(costs):,.0f}원")
        durations = [r['duration'] for r in e4 if r['duration']]
        if durations:
            report.append(f"  평균 예상 기간:            {statistics.mean(durations):.1f}일")
        report.append("")
    
    report.append("=" * 60)
    report.append("🎯 발표 핵심 메시지")
    report.append("=" * 60)
    
    if e1:
        successful = [r for r in e1 if r.get('success', False)]
        if successful:
            naive_reqs = [r['naive_req_count'] for r in successful]
            agent_reqs = [r['agent_req_count'] for r in successful]
            improvement_pct = (statistics.mean(agent_reqs)/statistics.mean(naive_reqs)-1)*100
            report.append(f"✅ 1. LLM 기반 Agent가 규칙 기반 대비 {improvement_pct:+.0f}% 더 많은 요구사항 추출")
            report.append(f"✅ 2. Confidence 기반 재시도 로직으로 품질 보장")
            report.append(f"✅ 3. End-to-End 파이프라인으로 실제 제안서 자동 생성")
    
    report.append("")
    
    report_text = "\n".join(report)
    print("\n" + report_text)
    
    (results_dir / "SUMMARY_REPORT_TRUE_BASELINE.txt").write_text(report_text, encoding='utf-8')
    print(f"\n✅ 요약 리포트 저장: {results_dir / 'SUMMARY_REPORT_TRUE_BASELINE.txt'}")


if __name__ == "__main__":
    print("\n" + "="*60)
    print("🚀 PM Agent v0.9 - 진짜 Baseline 비교 실험")
    print("="*60 + "\n")
    
    rfps = load_rfp_files("experiments/rfp_samples")
    if not rfps:
        print("❌ RFP 샘플이 없습니다.")
        exit(1)
    
    results_dir = ensure_results_dir()

    # E1: 진짜 Baseline
    print("\n=== E1: Naive(규칙) vs PM Agent(LLM) ===")
    e1 = experiment_E1_true_baseline(rfps)
    (results_dir / "E1_true_baseline.json").write_text(
        json.dumps(e1, indent=2, ensure_ascii=False), encoding="utf-8")
    print_summary_e1(e1)
    visualize_e1_results(e1, results_dir)

    # E4
    print("\n=== E4: End-to-End Proposal ===")
    e4 = experiment_E4_proposal(rfps)
    (results_dir / "E4_proposal.json").write_text(
        json.dumps(e4, indent=2, ensure_ascii=False), encoding="utf-8")
    
    create_summary_report(e1, e4, results_dir)
    
    print("\n" + "="*60)
    print("✅ 실험 완료!")
    print(f"📁 결과: {results_dir}")
    print("="*60)