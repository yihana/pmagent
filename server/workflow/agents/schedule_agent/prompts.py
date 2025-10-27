# server/workflow/agents/schedule_agent/prompts.py
# prompts.py (schedule agent prompts)
DURATION_DEP_PROMPT='''\n입력은 시간정보 없는 WBS입니다. 각 작업의 예상 기간(일)과 선행관계를 제안하세요.
가정:
- 업무 난이도: 보통
- 리소스: 표준 1 FTE 기준
- 방법론: {methodology} (agile이면 2주 스프린트 경계 고려)
출력 JSON 배열: [{id, duration_days, predecessors: [id,...]}]
입력 WBS:
{wbs_json}
'''
