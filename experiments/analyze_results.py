# scripts/analyze_results.py
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

def analyze_all_experiments():
    """모든 실험 결과 분석"""
    experiments_dir = Path("experiments")
    
    for exp_dir in experiments_dir.iterdir():
        if not exp_dir.is_dir():
            continue
        
        metrics_file = exp_dir / "metrics.csv"
        if not metrics_file.exists():
            continue
        
        print(f"\n{'='*60}")
        print(f"📊 {exp_dir.name}")
        print(f"{'='*60}")
        
        df = pd.read_csv(metrics_file)
        
        # 기본 통계
        print("\n기본 통계:")
        print(df.describe())
        
        # 그룹별 비교
        if 'method' in df.columns:
            print("\n방법별 비교:")
            print(df.groupby('method').mean())
        
        if 'technique' in df.columns:
            print("\n기법별 비교:")
            print(df.groupby('technique').mean())
        
        # 시각화
        create_visualizations(df, exp_dir)

def create_visualizations(df, output_dir):
    """결과 시각화"""
    sns.set_style("whitegrid")
    
    # 1. 처리 시간 비교
    if 'duration_seconds' in df.columns and 'method' in df.columns:
        plt.figure(figsize=(10, 6))
        sns.barplot(data=df, x='method', y='duration_seconds')
        plt.title('처리 시간 비교')
        plt.ylabel('시간 (초)')
        plt.tight_layout()
        plt.savefig(output_dir / 'duration_comparison.png', dpi=300)
        plt.close()
    
    # 2. 품질 메트릭 비교
    quality_cols = ['accuracy', 'requirement_count', 'wbs_task_count']
    available_cols = [col for col in quality_cols if col in df.columns]
    
    if available_cols and 'method' in df.columns:
        fig, axes = plt.subplots(1, len(available_cols), figsize=(15, 5))
        if len(available_cols) == 1:
            axes = [axes]
        
        for ax, col in zip(axes, available_cols):
            sns.barplot(data=df, x='method', y=col, ax=ax)
            ax.set_title(col.replace('_', ' ').title())
        
        plt.tight_layout()
        plt.savefig(output_dir / 'quality_metrics.png', dpi=300)
        plt.close()

if __name__ == "__main__":
    analyze_all_experiments()