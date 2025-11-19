# experiments/run_experiments.py

import json
import time
import asyncio
import statistics
from pathlib import Path
from typing import List, Dict, Any

from server.workflow.agents.scope_agent.pipeline import ScopeAgent
from server.workflow.agents.cost_agent.cost_agent import CostAgent
from server.workflow.agents.schedule_agent.pipeline import ScheduleAgent

import matplotlib.pyplot as plt
import matplotlib
matplotlib.rcParams['font.family'] = 'Malgun Gothic'
matplotlib.rcParams['axes.unicode_minus'] = False


# ------------------------------------------------------------
# 유틸
# ------------------------------------------------------------
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


# ------------------------------------------------------------
# E1: Scope 품질/효율 실험
#   - Baseline: pipeline 기본 호출 (옵션 없음)
#   - Deep: pipeline(ToT + Self-Refine 옵션)
# ------------------------------------------------------------
def experiment_E1_scope(rfps: List[str]) -> List[Dict[str, Any]]:
    """
    E1: Scope 품질 비교
    - Baseline: 단순 pipeline 호출 (옵션 없음)
    - Deep: pipeline + ToT/Self-Refine 옵션
    """
    scope = ScopeAgent()
    results = []

    for idx, rfp_text in enumerate(rfps):
        print(f"\n[E1] RFP #{idx} ---------------------------")
        
        try:
            # Baseline (옵션 없이 기본 pipeline)
            t0 = time.time()
            baseline = asyncio.run(
                scope.pipeline(
                    {
                        "project_id": f"E1-baseline-{idx}",
                        "text": rfp_text,
                        # 옵션 없음 - 기본 동작
                    }
                )
            )
            baseline_time = time.time() - t0
            baseline_req_count = len(baseline.get("requirements", []))
            print(f"  Baseline: req={baseline_req_count}, time={baseline_time:.2f}s")
            
        except Exception as e:
            print(f"  ❌ Baseline 실패: {e}")
            baseline_req_count = 0
            baseline_time = 0

        try:
            # Deep (ToT + Self-Refine 옵션 활성화)
            t1 = time.time()
            deep = asyncio.run(
                scope.pipeline(
                    {
                        "project_id": f"E1-deep-{idx}",
                        "text": rfp_text,
                        "options": {
                            "tot_constraints": {"max_time": 120, "min_quality": 0.85},
                            "refine_iterations": 2,
                        },
                    }
                )
            )
            deep_time = time.time() - t1
            deep_req_count = len(deep.get("requirements", []))
            print(f"  Deep:     req={deep_req_count}, time={deep_time:.2f}s")
            
        except Exception as e:
            print(f"  ❌ Deep 실패: {e}")
            deep_req_count = 0
            deep_time = 0

        results.append(
            {
                "rfp_id": idx,
                "baseline_req_count": baseline_req_count,
                "deep_req_count": deep_req_count,
                "baseline_time": baseline_time,
                "deep_time": deep_time,
                "success": baseline_req_count > 0 and deep_req_count > 0
            }
        )

    return results


# ------------------------------------------------------------
# E2: Schedule Baseline vs GoT
#   - baseline: use_got=False
#   - got:      use_got=True
#   ※ requirements/WBS는 이미 Scope/WBS 단계에서 data/{project_id}/에 생성되었다고 가정
# ------------------------------------------------------------
def experiment_E2_schedule(rfps: List[str]) -> List[Dict[str, Any]]:
    sched = ScheduleAgent()
    results = []

    for idx, _rfp_text in enumerate(rfps):
        project_id = f"E2-{idx}"
        base_dir = Path("data") / project_id
        req_json = base_dir / "requirements.json"
        wbs_json = base_dir / "wbs_structure.json"

        if not req_json.exists() or not wbs_json.exists():
            print(f"[WARN] E2: {project_id} requirements/wbs json not found, skip.")
            continue

        print(f"\n[E2] Project {project_id} ---------------------------")

        try:
            # Baseline
            baseline_payload = {
                "project_id": project_id,
                "methodology": "waterfall",
                "requirements_json": str(req_json),
                "wbs_json": str(wbs_json),
                "calendar": {"start_date": "2025-11-18"},
                "sprint_length_weeks": 2,
                "estimation_mode": "heuristic",
                "use_got": False,
            }
            base = sched.create_schedule_from_payload(baseline_payload)
            base_duration = base.get("total_duration", None)

            # GoT (use_got=True)
            got_payload = dict(baseline_payload)
            got_payload["use_got"] = True
            got = sched.create_schedule_from_payload(got_payload)
            got_duration = got.get("total_duration", None)
            got_candidates = len(got.get("candidates", [])) if "candidates" in got else None

            print(f"  Baseline duration: {base_duration}")
            print(f"  GoT duration:      {got_duration} (candidates={got_candidates})")

            results.append(
                {
                    "project_id": project_id,
                    "baseline_duration": base_duration,
                    "got_best_duration": got_duration,
                    "num_candidates": got_candidates,
                }
            )
        except Exception as e:
            print(f"  ❌ E2 실패: {e}")

    return results


# ------------------------------------------------------------
# E3: Efficiency (Scope 실행시간 비교만 따로)
# ------------------------------------------------------------
def experiment_E3_efficiency(e1_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    results = []
    for row in e1_results:
        results.append(
            {
                "rfp_id": row["rfp_id"],
                "baseline_time": row["baseline_time"],
                "deep_time": row["deep_time"],
            }
        )
    return results


# ------------------------------------------------------------
# E4: End-to-End Proposal (Scope → Cost → Schedule)
# ------------------------------------------------------------
def experiment_E4_proposal(rfps: List[str]) -> List[Dict[str, Any]]:
    scope = ScopeAgent()
    cost = CostAgent()
    sched = ScheduleAgent()

    results = []

    for idx, rfp_text in enumerate(rfps):
        project_id = f"E4-{idx}"
        print(f"\n[E4] Project {project_id} ---------------------------")

        try:
            # Scope
            out = asyncio.run(
                scope.pipeline(
                    {
                        "project_id": project_id,
                        "text": rfp_text,
                    }
                )
            )
            reqs = out.get("requirements", [])

            # Cost
            cost_out = cost.estimate_cost(reqs)

            # Schedule (단순 heuristic)
            sched_out = sched.create_schedule(reqs)

            results.append(
                {
                    "project_id": project_id,
                    "req_count": len(reqs),
                    "total_cost": cost_out.get("total_cost"),
                    "duration": sched_out.get("total_duration"),
                }
            )

            print(
                f"  req={len(reqs)}, cost={cost_out.get('total_cost')}, "
                f"duration={sched_out.get('total_duration')}"
            )
        except Exception as e:
            print(f"  ❌ E4 실패: {e}")

    return results


# ------------------------------------------------------------
# 통계 요약 출력
# ------------------------------------------------------------
def print_summary_e1(e1: List[Dict[str, Any]]):
    # 성공한 케이스만 필터링
    successful = [r for r in e1 if r.get('success', False)]
    
    if not successful:
        print("[SUMMARY] E1: no successful data")
        return

    base_reqs = [r["baseline_req_count"] for r in successful]
    deep_reqs = [r["deep_req_count"] for r in successful]
    base_t = [r["baseline_time"] for r in successful]
    deep_t = [r["deep_time"] for r in successful]

    print("\n[SUMMARY] E1 Scope Quality/Efficiency")
    print(f"  성공 케이스: {len(successful)}/{len(e1)}")
    print(f"  Baseline req avg: {statistics.mean(base_reqs):.2f}")
    print(f"  Deep req avg:     {statistics.mean(deep_reqs):.2f}")
    print(f"  개선율:           {(statistics.mean(deep_reqs)/statistics.mean(base_reqs)-1)*100:.1f}%")
    print(f"  Baseline time avg:{statistics.mean(base_t):.2f}s")
    print(f"  Deep time avg:    {statistics.mean(deep_t):.2f}s")


def visualize_e1_results(e1_results: List[Dict[str, Any]], results_dir: Path):
    """E1 결과 시각화: 요구사항 수 & 시간 비교"""
    # 성공한 케이스만 필터링
    successful = [r for r in e1_results if r.get('success', False)]
    
    if not successful:
        print("⚠️  E1: 시각화할 성공 데이터 없음")
        return
    
    rfp_ids = [r['rfp_id'] for r in successful]
    baseline_reqs = [r['baseline_req_count'] for r in successful]
    deep_reqs = [r['deep_req_count'] for r in successful]
    baseline_times = [r['baseline_time'] for r in successful]
    deep_times = [r['deep_time'] for r in successful]
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    
    # 요구사항 수 비교
    x = range(len(rfp_ids))
    width = 0.35
    ax1.bar([i - width/2 for i in x], baseline_reqs, width, label='Baseline', alpha=0.8)
    ax1.bar([i + width/2 for i in x], deep_reqs, width, label='Deep (ToT+Refine)', alpha=0.8)
    ax1.set_xlabel('RFP ID')
    ax1.set_ylabel('요구사항 개수')
    ax1.set_title('E1: 요구사항 추출 개수 비교')
    ax1.set_xticks(x)
    ax1.set_xticklabels([f'RFP {i}' for i in rfp_ids])
    ax1.legend()
    ax1.grid(axis='y', alpha=0.3)
    
    # 처리 시간 비교
    ax2.bar([i - width/2 for i in x], baseline_times, width, label='Baseline', alpha=0.8)
    ax2.bar([i + width/2 for i in x], deep_times, width, label='Deep (ToT+Refine)', alpha=0.8)
    ax2.set_xlabel('RFP ID')
    ax2.set_ylabel('처리 시간 (초)')
    ax2.set_title('E1: 처리 시간 비교')
    ax2.set_xticks(x)
    ax2.set_xticklabels([f'RFP {i}' for i in rfp_ids])
    ax2.legend()
    ax2.grid(axis='y', alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(results_dir / 'E1_visualization.png', dpi=300, bbox_inches='tight')
    plt.close()
    print(f"✅ E1 시각화 저장: {results_dir / 'E1_visualization.png'}")


def visualize_e2_results(e2_results: List[Dict[str, Any]], results_dir: Path):
    """E2 결과 시각화: 스케줄 기간 비교"""
    if not e2_results:
        print("⚠️  E2: 시각화할 데이터 없음")
        return
    
    projects = [r['project_id'] for r in e2_results]
    baseline_durations = [r['baseline_duration'] for r in e2_results]
    got_durations = [r['got_best_duration'] for r in e2_results]
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    x = range(len(projects))
    width = 0.35
    ax.bar([i - width/2 for i in x], baseline_durations, width, 
           label='Baseline', alpha=0.8, color='#ff7f0e')
    ax.bar([i + width/2 for i in x], got_durations, width, 
           label='GoT Best', alpha=0.8, color='#2ca02c')
    
    # 개선율 텍스트 추가
    for i, (base, got) in enumerate(zip(baseline_durations, got_durations)):
        if base and got:
            improvement = ((base - got) / base) * 100
            ax.text(i, max(base, got) + 2, f'{improvement:.1f}%↓', 
                   ha='center', fontsize=9, color='red' if improvement > 0 else 'gray')
    
    ax.set_xlabel('Project ID')
    ax.set_ylabel('총 기간 (일)')
    ax.set_title('E2: Schedule 생성 - Baseline vs GoT')
    ax.set_xticks(x)
    ax.set_xticklabels(projects, rotation=45, ha='right')
    ax.legend()
    ax.grid(axis='y', alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(results_dir / 'E2_visualization.png', dpi=300, bbox_inches='tight')
    plt.close()
    print(f"✅ E2 시각화 저장: {results_dir / 'E2_visualization.png'}")


def create_summary_report(e1, e2, e3, e4, results_dir: Path):
    """발표용 요약 리포트 생성"""
    report = []
    report.append("=" * 60)
    report.append("PM Agent v0.9 실험 결과 요약 리포트")
    report.append("=" * 60)
    report.append("")
    
    # E1 요약
    if e1:
        successful = [r for r in e1 if r.get('success', False)]
        if successful:
            base_reqs = [r['baseline_req_count'] for r in successful]
            deep_reqs = [r['deep_req_count'] for r in successful]
            base_times = [r['baseline_time'] for r in successful]
            deep_times = [r['deep_time'] for r in successful]
            
            report.append("📊 E1: Scope 품질/효율성")
            report.append("-" * 60)
            report.append(f"  성공 케이스:               {len(successful)}/{len(e1)}개")
            report.append(f"  Baseline 평균 요구사항 수: {statistics.mean(base_reqs):.1f}개")
            report.append(f"  Deep 평균 요구사항 수:     {statistics.mean(deep_reqs):.1f}개")
            report.append(f"  개선율:                    {(statistics.mean(deep_reqs)/statistics.mean(base_reqs)-1)*100:.1f}% 증가")
            report.append("")
            report.append(f"  Baseline 평균 처리 시간:   {statistics.mean(base_times):.1f}초")
            report.append(f"  Deep 평균 처리 시간:       {statistics.mean(deep_times):.1f}초")
            report.append(f"  시간 오버헤드:             {(statistics.mean(deep_times)/statistics.mean(base_times)-1)*100:.1f}%")
            report.append("")
    
    # E2 요약
    if e2:
        valid_e2 = [r for r in e2 if r['baseline_duration'] and r['got_best_duration']]
        if valid_e2:
            base_durs = [r['baseline_duration'] for r in valid_e2]
            got_durs = [r['got_best_duration'] for r in valid_e2]
            
            report.append("📊 E2: Schedule 최적화 (GoT)")
            report.append("-" * 60)
            report.append(f"  Baseline 평균 기간:        {statistics.mean(base_durs):.1f}일")
            report.append(f"  GoT Best 평균 기간:        {statistics.mean(got_durs):.1f}일")
            report.append(f"  기간 단축:                 {(1-statistics.mean(got_durs)/statistics.mean(base_durs))*100:.1f}%")
            
            candidates = [r['num_candidates'] for r in valid_e2 if r['num_candidates']]
            if candidates:
                report.append(f"  평균 후보 스케줄 개수:     {statistics.mean(candidates):.1f}개")
            report.append("")
    
    # E4 요약
    if e4:
        report.append("📊 E4: End-to-End Proposal 생성")
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
    report.append("🎯 발표 핵심 메시지 검증")
    report.append("=" * 60)
    
    if e1:
        successful = [r for r in e1 if r.get('success', False)]
        if successful:
            base_reqs = [r['baseline_req_count'] for r in successful]
            deep_reqs = [r['deep_req_count'] for r in successful]
            improvement = (statistics.mean(deep_reqs)/statistics.mean(base_reqs)-1)*100
            report.append(f"✅ 1. Agent 문제 이해: Baseline 대비 Deep 방식이 {improvement:.0f}% 더 많은 요구사항 추출")
    
    if e2:
        valid_e2 = [r for r in e2 if r['baseline_duration'] and r['got_best_duration']]
        if valid_e2:
            base_durs = [r['baseline_duration'] for r in valid_e2]
            got_durs = [r['got_best_duration'] for r in valid_e2]
            reduction = (1-statistics.mean(got_durs)/statistics.mean(base_durs))*100
            report.append(f"✅ 2. 최신 논문 적용: GoT 적용으로 스케줄 기간 {reduction:.0f}% 단축")
    
    report.append(f"✅ 3. 정량적 검증: 총 {len(e1) if e1 else 0}개 RFP 샘플로 반복 실험 완료")
    report.append("")
    
    report_text = "\n".join(report)
    
    # 콘솔 출력
    print("\n" + report_text)
    
    # 파일 저장
    (results_dir / "SUMMARY_REPORT.txt").write_text(
        report_text, 
        encoding='utf-8'
    )
    print(f"\n✅ 요약 리포트 저장: {results_dir / 'SUMMARY_REPORT.txt'}")


# ------------------------------------------------------------
# MAIN
# ------------------------------------------------------------
if __name__ == "__main__":
    print("\n" + "="*60)
    print("🚀 PM Agent v0.9 정량 실험 시작")
    print("="*60 + "\n")
    
    # RFP 로드
    rfps = load_rfp_files("experiments/rfp_samples")
    if not rfps:
        print("❌ RFP 샘플이 없습니다. experiments/rfp_samples/*.txt 파일을 준비해주세요.")
        exit(1)
    
    results_dir = ensure_results_dir()

    # E1
    print("\n=== E1: Scope Quality ===")
    e1 = experiment_E1_scope(rfps)
    (results_dir / "E1_scope.json").write_text(
        json.dumps(e1, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print_summary_e1(e1)
    visualize_e1_results(e1, results_dir)

    # E2
    print("\n=== E2: Schedule GoT ===")
    e2 = experiment_E2_schedule(rfps)
    (results_dir / "E2_schedule.json").write_text(
        json.dumps(e2, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    visualize_e2_results(e2, results_dir)

    # E3 (E1 시간 데이터 요약)
    print("\n=== E3: Efficiency (Scope Time) ===")
    e3 = experiment_E3_efficiency(e1)
    (results_dir / "E3_efficiency.json").write_text(
        json.dumps(e3, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # E4
    print("\n=== E4: End-to-End Proposal ===")
    e4 = experiment_E4_proposal(rfps)
    (results_dir / "E4_proposal.json").write_text(
        json.dumps(e4, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    
    # 통합 리포트 생성
    create_summary_report(e1, e2, e3, e4, results_dir)
    
    print("\n" + "="*60)
    print("✅ 모든 실험 완료!")
    print(f"📁 결과 저장 위치: {results_dir}")
    print("📊 생성된 파일:")
    print(f"  - JSON 데이터: E1~E4.json")
    print(f"  - 시각화: E1_visualization.png, E2_visualization.png")
    print(f"  - 요약 리포트: SUMMARY_REPORT.txt")
    print("="*60)