BEGIN TRANSACTION;

-- 프로젝트
CREATE TABLE IF NOT EXISTS pm_projects (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TEXT
);

-- 문서 (회의록 등)
CREATE TABLE IF NOT EXISTS pm_documents (
    id INTEGER PRIMARY KEY,
    project_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    path TEXT,
    doc_type TEXT NOT NULL,
    created_at TEXT,
    uploaded_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_pm_documents_project ON pm_documents(project_id);

-- 회의(매팅) 테이블
CREATE TABLE IF NOT EXISTS pm_meetings (
    id INTEGER PRIMARY KEY,
    project_id INTEGER NOT NULL,
    date TEXT NOT NULL,
    title TEXT NOT NULL,
    raw_text TEXT NOT NULL,
    parsed_json TEXT,
    created_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_pm_meetings_project ON pm_meetings(project_id);

-- 액션 아이템
CREATE TABLE IF NOT EXISTS pm_action_items (
    id INTEGER PRIMARY KEY,
    project_id INTEGER NOT NULL,
    document_id INTEGER,
    meeting_id INTEGER,
    assignee TEXT,
    task TEXT NOT NULL,
    due_date TEXT,
    priority TEXT,
    status TEXT,
    module TEXT,
    phase TEXT,
    evidence_span TEXT,
    expected_effort REAL,
    expected_value REAL,
    created_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_pm_action_items_project ON pm_action_items(project_id);
CREATE INDEX IF NOT EXISTS idx_pm_action_items_meeting ON pm_action_items(meeting_id);

-- 후속(Follow-up) 항목
CREATE TABLE IF NOT EXISTS pm_fup_items (
    id INTEGER PRIMARY KEY,
    meeting_id INTEGER NOT NULL,
    assignee TEXT,
    task TEXT NOT NULL,
    due_date TEXT,
    priority TEXT,
    status TEXT,
    evidence_span TEXT
);
CREATE INDEX IF NOT EXISTS idx_pm_fup_meeting ON pm_fup_items(meeting_id);

-- 리스크
CREATE TABLE IF NOT EXISTS pm_risks (
    id INTEGER PRIMARY KEY,
    project_id INTEGER NOT NULL,
    risk TEXT NOT NULL,
    owner TEXT,
    impact TEXT,
    likelihood TEXT,
    mitigation TEXT,
    due_date TEXT,
    status TEXT,
    created_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_pm_risks_project ON pm_risks(project_id);

-- Scope Agent 결과
CREATE TABLE IF NOT EXISTS pm_scope (
    id INTEGER PRIMARY KEY,
    project_id INTEGER NOT NULL,
    scope_statement_md TEXT,
    rtm_csv TEXT,
    wbs_json TEXT,
    wbs_excel TEXT,
    rtm_excel TEXT,
    scope_statement_excel TEXT,
    project_charter_docx TEXT,
    tailoring_excel TEXT,
    full_json TEXT,
    created_at TEXT,
    updated_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_pm_scope_project ON pm_scope(project_id);

-- Schedule Agent 결과
CREATE TABLE IF NOT EXISTS pm_schedule (
    id INTEGER PRIMARY KEY,
    project_id INTEGER NOT NULL,
    methodology TEXT DEFAULT 'waterfall',
    plan_csv TEXT,
    gantt_json TEXT,
    critical_path TEXT,
    burndown_json TEXT,
    change_management_excel TEXT,
    full_json TEXT,
    created_at TEXT,
    updated_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_pm_schedule_project ON pm_schedule(project_id);

-- Task (WBS)
CREATE TABLE IF NOT EXISTS pm_tasks (
    id TEXT PRIMARY KEY,
    project_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    type TEXT,
    parent_id TEXT,
    duration_days INTEGER,
    story_points INTEGER,
    es INTEGER,
    ef INTEGER,
    ls INTEGER,
    lf INTEGER,
    float REAL,
    planned_start TEXT,
    planned_end TEXT,
    actual_start TEXT,
    actual_end TEXT,
    status TEXT,
    progress INTEGER,
    assignee TEXT,
    created_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_pm_tasks_project ON pm_tasks(project_id);

-- Task Links
CREATE TABLE IF NOT EXISTS pm_task_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    predecessor_id TEXT NOT NULL,
    successor_id TEXT NOT NULL,
    link_type TEXT DEFAULT 'FS',
    lag_days INTEGER DEFAULT 0,
    created_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_pm_task_links_project ON pm_task_links(project_id);

-- Sprint
CREATE TABLE IF NOT EXISTS pm_sprints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    sprint_no INTEGER NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    committed_sp INTEGER DEFAULT 0,
    completed_sp INTEGER DEFAULT 0,
    status TEXT DEFAULT 'Planned',
    created_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_pm_sprints_project ON pm_sprints(project_id);

-- Output versions
CREATE TABLE IF NOT EXISTS pm_output_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    version_tag TEXT NOT NULL,
    output_type TEXT NOT NULL,
    files_json TEXT,
    generated_at TEXT,
    generated_by TEXT
);
CREATE INDEX IF NOT EXISTS idx_pm_output_versions_project ON pm_output_versions(project_id);

-- Logs
CREATE TABLE IF NOT EXISTS pm_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT,
    message TEXT,
    details TEXT,
    created_at TEXT
);

COMMIT;
