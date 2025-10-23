# create_fresh_pm_db.ps1
# PMP Agent용 새로운 DB를 생성하는 스크립트
#
# 사용법:
#   .\create_fresh_pm_db.ps1
#   .\create_fresh_pm_db.ps1 -DBPath "custom.db"

param(
    [string]$DBPath = "pm_agent.db",
    [switch]$Force = $false
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "PM Agent Fresh DB Creation Script" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 현재 디렉토리
$CurrentDir = Get-Location

# DB 경로 설정
if (-not [System.IO.Path]::IsPathRooted($DBPath)) {
    $DBPath = Join-Path $CurrentDir $DBPath
}

Write-Host "[INFO] Target DB Path: $DBPath" -ForegroundColor Yellow

# 기존 DB 존재 확인
if (Test-Path $DBPath) {
    if ($Force) {
        Write-Host "[WARN] Existing DB will be overwritten!" -ForegroundColor Yellow
        $BackupPath = "$DBPath.old_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
        Move-Item $DBPath $BackupPath -Force
        Write-Host "[OK] Old DB moved to: $BackupPath" -ForegroundColor Green
    } else {
        Write-Host "[ERROR] DB already exists: $DBPath" -ForegroundColor Red
        Write-Host "[INFO] Use -Force flag to overwrite" -ForegroundColor Yellow
        exit 1
    }
}

# Python 스크립트로 전체 DB 생성
$PythonScript = @"
import sqlite3
from pathlib import Path

db_path = r'$DBPath'
print(f'[INFO] Creating new database: {db_path}')

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 전체 테이블 생성 SQL
create_tables_sql = '''
BEGIN TRANSACTION;

-- Projects
CREATE TABLE pm_projects (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Documents
CREATE TABLE pm_documents (
    id INTEGER PRIMARY KEY,
    project_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    path TEXT,
    doc_type TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES pm_projects(id)
);

-- Meetings
CREATE TABLE pm_meetings (
    id INTEGER PRIMARY KEY,
    project_id INTEGER NOT NULL,
    date TEXT NOT NULL,
    title TEXT NOT NULL,
    raw_text TEXT NOT NULL,
    parsed_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES pm_projects(id)
);

-- Action Items
CREATE TABLE pm_action_items (
    id INTEGER PRIMARY KEY,
    project_id INTEGER NOT NULL,
    document_id INTEGER,
    meeting_id INTEGER,
    assignee TEXT,
    task TEXT NOT NULL,
    due_date TEXT,
    priority TEXT DEFAULT 'Medium',
    status TEXT DEFAULT 'Open',
    module TEXT,
    phase TEXT,
    evidence_span TEXT,
    expected_effort REAL,
    expected_value REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (document_id) REFERENCES pm_documents(id),
    FOREIGN KEY (meeting_id) REFERENCES pm_meetings(id)
);

-- Follow-up Items
CREATE TABLE pm_fup_items (
    id INTEGER PRIMARY KEY,
    meeting_id INTEGER NOT NULL,
    assignee TEXT,
    task TEXT NOT NULL,
    due_date TEXT,
    priority TEXT,
    status TEXT DEFAULT 'Open',
    evidence_span TEXT,
    FOREIGN KEY (meeting_id) REFERENCES pm_meetings(id)
);

-- Risks
CREATE TABLE pm_risks (
    id INTEGER PRIMARY KEY,
    project_id INTEGER NOT NULL,
    risk TEXT NOT NULL,
    owner TEXT,
    impact TEXT,
    likelihood TEXT,
    mitigation TEXT,
    due_date TEXT,
    status TEXT DEFAULT 'Open',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Scope Results
CREATE TABLE pm_scope (
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
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Schedule Results
CREATE TABLE pm_schedule (
    id INTEGER PRIMARY KEY,
    project_id INTEGER NOT NULL,
    methodology TEXT DEFAULT 'waterfall',
    plan_csv TEXT,
    gantt_json TEXT,
    critical_path TEXT,
    burndown_json TEXT,
    change_management_excel TEXT,
    full_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tasks (WBS Items)
CREATE TABLE pm_tasks (
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
    status TEXT DEFAULT 'Not Started',
    progress INTEGER DEFAULT 0,
    assignee TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Task Links (Dependencies)
CREATE TABLE pm_task_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    predecessor_id TEXT NOT NULL,
    successor_id TEXT NOT NULL,
    link_type TEXT DEFAULT 'FS',
    lag_days INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Sprints (Agile)
CREATE TABLE pm_sprints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    sprint_no INTEGER NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    committed_sp INTEGER DEFAULT 0,
    completed_sp INTEGER DEFAULT 0,
    status TEXT DEFAULT 'Planned',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Output Versions
CREATE TABLE pm_output_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    version_tag TEXT NOT NULL,
    output_type TEXT NOT NULL,
    files_json TEXT,
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    generated_by TEXT
);

-- Logs
CREATE TABLE pm_logs (
    id INTEGER PRIMARY KEY,
    event_type TEXT,
    message TEXT,
    details TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX idx_pm_tasks_project ON pm_tasks(project_id);
CREATE INDEX idx_pm_task_links_project ON pm_task_links(project_id);
CREATE INDEX idx_pm_sprints_project ON pm_sprints(project_id);
CREATE INDEX idx_pm_output_versions_project ON pm_output_versions(project_id);

COMMIT;
'''

try:
    cursor.executescript(create_tables_sql)
    print('[OK] All tables created successfully')
    
    # 테이블 목록 확인
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = cursor.fetchall()
    
    print('')
    print('[INFO] Created tables:')
    for table in tables:
        print(f'  - {table[0]}')
    
    conn.close()
    print('')
    print('[SUCCESS] Database created successfully!')
    
except Exception as e:
    print(f'[ERROR] Failed to create database: {e}')
    import traceback
    traceback.print_exc()
    exit(1)
"@

$TempPyFile = Join-Path $env:TEMP "create_pm_db_temp.py"
$PythonScript | Out-File -FilePath $TempPyFile -Encoding UTF8

Write-Host "[INFO] Creating database..." -ForegroundColor Yellow

try {
    $result = python $TempPyFile 2>&1
    Write-Host $result
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host ""
        Write-Host "========================================" -ForegroundColor Green
        Write-Host "Database created successfully!" -ForegroundColor Green
        Write-Host "========================================" -ForegroundColor Green
        Write-Host ""
        Write-Host "[OK] Database: $DBPath" -ForegroundColor Cyan
        Write-Host "[INFO] You can now start using PM Agent" -ForegroundColor Cyan
    } else {
        Write-Host ""
        Write-Host "[ERROR] Database creation failed!" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "[ERROR] Python execution failed: $_" -ForegroundColor Red
    exit 1
} finally {
    if (Test-Path $TempPyFile) {
        Remove-Item $TempPyFile -Force
    }
}

Write-Host ""