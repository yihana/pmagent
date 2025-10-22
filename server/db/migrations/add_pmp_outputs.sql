-- server/db/migrations/add_pmp_outputs.sql
-- PMP 표준 산출물 지원을 위한 DB 마이그레이션

BEGIN TRANSACTION;

-- ✅ pm_scope 테이블에 PMP 산출물 컬럼 추가
ALTER TABLE pm_scope ADD COLUMN wbs_excel TEXT;
ALTER TABLE pm_scope ADD COLUMN rtm_excel TEXT;
ALTER TABLE pm_scope ADD COLUMN scope_statement_excel TEXT;
ALTER TABLE pm_scope ADD COLUMN project_charter_docx TEXT;
ALTER TABLE pm_scope ADD COLUMN tailoring_excel TEXT;
ALTER TABLE pm_scope ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

-- ✅ pm_schedule 테이블에 PMP 산출물 컬럼 추가
ALTER TABLE pm_schedule ADD COLUMN methodology TEXT DEFAULT 'waterfall';
ALTER TABLE pm_schedule ADD COLUMN burndown_json TEXT;
ALTER TABLE pm_schedule ADD COLUMN change_management_excel TEXT;
ALTER TABLE pm_schedule ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

-- ✅ Task 테이블 생성 (WBS 아이템별 상세 정보)
CREATE TABLE IF NOT EXISTS pm_tasks (
    id TEXT PRIMARY KEY,
    project_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    type TEXT,  -- phase/task/deliverable
    parent_id TEXT,
    
    -- 일정 정보
    duration_days INTEGER,
    story_points INTEGER,
    
    -- CPM 계산 결과
    es INTEGER,
    ef INTEGER,
    ls INTEGER,
    lf INTEGER,
    float REAL,
    
    -- 실제 일정
    planned_start TEXT,
    planned_end TEXT,
    actual_start TEXT,
    actual_end TEXT,
    
    -- 상태
    status TEXT DEFAULT 'Not Started',
    progress INTEGER DEFAULT 0,
    assignee TEXT,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_pm_tasks_project ON pm_tasks(project_id);

-- ✅ Task 선후행 관계 테이블
CREATE TABLE IF NOT EXISTS pm_task_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    predecessor_id TEXT NOT NULL,
    successor_id TEXT NOT NULL,
    link_type TEXT DEFAULT 'FS',  -- FS/SS/FF/SF
    lag_days INTEGER DEFAULT 0,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_pm_task_links_project ON pm_task_links(project_id);

-- ✅ Sprint 테이블 (Agile 전용)
CREATE TABLE IF NOT EXISTS pm_sprints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    sprint_no INTEGER NOT NULL,
    
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    
    committed_sp INTEGER DEFAULT 0,
    completed_sp INTEGER DEFAULT 0,
    
    status TEXT DEFAULT 'Planned',  -- Planned/Active/Completed
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_pm_sprints_project ON pm_sprints(project_id);

-- ✅ 산출물 버전 관리 테이블
CREATE TABLE IF NOT EXISTS pm_output_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    version_tag TEXT NOT NULL,
    output_type TEXT NOT NULL,  -- scope/schedule/report
    
    files_json TEXT,  -- JSON 형태로 파일 경로 저장
    
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    generated_by TEXT
);

CREATE INDEX IF NOT EXISTS idx_pm_output_versions_project ON pm_output_versions(project_id);

COMMIT;