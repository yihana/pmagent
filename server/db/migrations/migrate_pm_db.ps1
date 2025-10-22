# migrate_pm_db.ps1
# PMP 표준 산출물 지원을 위한 DB 마이그레이션 스크립트
#
# 사용법:
#   .\migrate_pm_db.ps1
#   .\migrate_pm_db.ps1 -DBPath "custom_path.db"
#   .\migrate_pm_db.ps1 -DBPath "history.db" -Force

param(
    [string]$DBPath = "pm_agent.db",
    [switch]$Force = $false
)

Set-StrictMode -Version Latest

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "PM Agent DB Migration Script" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 1. 현재 디렉토리 확인
$CurrentDir = Get-Location
Write-Host "[INFO] Current Directory: $CurrentDir" -ForegroundColor Yellow

# 2. DB 파일 경로 설정 (절대경로로 변환)
if (-not [System.IO.Path]::IsPathRooted($DBPath)) {
    $DBPath = Join-Path $CurrentDir $DBPath
}
Write-Host "[INFO] DB Path: $DBPath" -ForegroundColor Yellow

# 3. DB 파일 존재 확인 및 백업
if (Test-Path $DBPath) {
    Write-Host "[INFO] Database file exists." -ForegroundColor Yellow
    if (-not $Force) {
        # 백업 (파일명에 타임스탬프 추가)
        $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
        $backupPath = "$DBPath.bak.$timestamp"
        Copy-Item -Path $DBPath -Destination $backupPath -ErrorAction Stop
        Write-Host "[INFO] Backup created at: $backupPath" -ForegroundColor Green
    } else {
        Write-Host "[WARN] Force flag provided. Proceeding without creating the standard backup." -ForegroundColor Yellow
        # but still create a timestamped backup for safety
        $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
        $backupPath = "$DBPath.forcebak.$timestamp"
        Copy-Item -Path $DBPath -Destination $backupPath -ErrorAction SilentlyContinue
        if (Test-Path $backupPath) {
            Write-Host "[INFO] Force backup created at: $backupPath" -ForegroundColor Green
        }
    }
} else {
    Write-Host "[INFO] Database file does not exist. It will be created by migration." -ForegroundColor Yellow
}

# 4. 마이그레이션 SQL 파일 내용 (내장)
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$migrationsDir = Join-Path $scriptDir "db_migrations"
if (-not (Test-Path $migrationsDir)) {
    New-Item -ItemType Directory -Path $migrationsDir | Out-Null
}

$sqlFile = Join-Path $migrationsDir "create_pm_schedule_tables.sql"

$sqlContent = @"
BEGIN TRANSACTION;

CREATE TABLE IF NOT EXISTS pm_tasks (
    id TEXT PRIMARY KEY,
    project_id INTEGER,
    name TEXT,
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
    status TEXT,
    assignee TEXT
);

CREATE TABLE IF NOT EXISTS pm_task_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER,
    predecessor_id TEXT,
    successor_id TEXT
);

CREATE TABLE IF NOT EXISTS pm_sprints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER,
    sprint_no INTEGER,
    start_date TEXT,
    end_date TEXT,
    committed_sp INTEGER,
    completed_sp INTEGER,
    status TEXT
);

CREATE TABLE IF NOT EXISTS pm_schedule_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER,
    version_tag TEXT,
    generated_at TEXT,
    files_json TEXT
);

COMMIT;
"@

# write SQL file (overwrite if exists)
$sqlContent | Out-File -FilePath $sqlFile -Encoding UTF8 -Force
Write-Host "[INFO] Migration SQL written to: $sqlFile" -ForegroundColor Green

# 5. 임시 Python 스크립트 생성: sqlite3를 사용하여 SQL 실행 + 컬럼 체크/ALTER 수행
$pyFile = Join-Path $migrationsDir "apply_migration.py"
$pyContent = @"
#!/usr/bin/env python3
import sqlite3, sys, json, os
from pathlib import Path

def apply_sql(db_path, sql_path):
    print('Applying SQL:', sql_path)
    conn = sqlite3.connect(db_path)
    try:
        with open(sql_path, 'r', encoding='utf-8') as f:
            sql = f.read()
        conn.executescript(sql)
        conn.commit()
        print('SQL applied successfully.')
    except Exception as e:
        conn.rollback()
        print('ERROR applying SQL:', e)
        raise
    finally:
        conn.close()

def ensure_column(db_path, table, column, col_type):
    """
    If column not exists in table, run ALTER TABLE to add it.
    SQLite supports ALTER TABLE ADD COLUMN.
    """
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    try:
        cur.execute("PRAGMA table_info(%s)" % table)
        cols = [r[1] for r in cur.fetchall()]
        print(f'Existing columns for {table}:', cols)
        if column in cols:
            print(f'Column {column} already exists in {table}.')
            return
        stmt = f"ALTER TABLE {table} ADD COLUMN {column} {col_type};"
        print('Executing:', stmt)
        cur.execute(stmt)
        conn.commit()
        print(f'Added column {column} to {table}.')
    except Exception as e:
        conn.rollback()
        print(f'ERROR ensuring column {column} on {table}:', e)
        raise
    finally:
        conn.close()

def main(argv):
    if len(argv) < 3:
        print('Usage: apply_migration.py DB_PATH SQL_PATH')
        return 2
    db_path = argv[1]
    sql_path = argv[2]
    db_path = os.path.abspath(db_path)
    print('DB path:', db_path)
    # ensure directory exists
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
    apply_sql(db_path, sql_path)

    # Ensure legacy-required columns (based on issues observed)
    # 1) pm_documents.path TEXT
    try:
        ensure_column(db_path, 'pm_documents', 'path', 'TEXT')
    except Exception as e:
        print('Warning: could not ensure pm_documents.path:', e)

    # 2) pm_action_items.meeting_id INTEGER
    try:
        ensure_column(db_path, 'pm_action_items', 'meeting_id', 'INTEGER')
    except Exception as e:
        print('Warning: could not ensure pm_action_items.meeting_id:', e)

    print('Migration finished.')
    return 0

if __name__ == \"__main__\":
    sys.exit(main(sys.argv))
"@

# write python file
$pyContent | Out-File -FilePath $pyFile -Encoding UTF8 -Force
Write-Host "[INFO] Helper Python migration script written to: $pyFile" -ForegroundColor Green

# 6. Python 실행 가능 확인
$pythonExe = "python"
try {
    $pyVersion = & $pythonExe -c "import sys; print(sys.version.splitlines()[0])" 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Python not found or failed to run."
    }
    Write-Host "[INFO] Using Python: $pyVersion" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Python is required but was not found on PATH. Install Python 3 and ensure 'python' is available." -ForegroundColor Red
    exit 1
}

# 7. 실제 마이그레이션 실행 (Python 스크립트 호출)
try {
    $cmd = @($pythonExe, $pyFile, $DBPath, $sqlFile)
    Write-Host "[INFO] Running migration..." -ForegroundColor Cyan
    $proc = Start-Process -FilePath $pythonExe -ArgumentList @($pyFile, $DBPath, $sqlFile) -NoNewWindow -Wait -PassThru
    if ($proc.ExitCode -eq 0) {
        Write-Host "[SUCCESS] Migration applied successfully." -ForegroundColor Green
    } else {
        Write-Host "[ERROR] Migration script exited with code $($proc.ExitCode)." -ForegroundColor Red
        exit $proc.ExitCode
    }
} catch {
    Write-Host "[ERROR] Failed to run migration: $_" -ForegroundColor Red
    exit 2
}

# 8. 최종 확인: 테이블/컬럼 존재 여부 간단 조회 (python one-liner)
try {
    Write-Host "[INFO] Post-check: listing tables and selected columns..." -ForegroundColor Cyan
    $checkCmd = @"
import sqlite3, sys, os
db='$DBPath'
conn=sqlite3.connect(db)
cur=conn.cursor()
print('Tables:', [r[0] for r in cur.execute(\"SELECT name FROM sqlite_master WHERE type='table';\").fetchall()])
for t in ['pm_documents','pm_action_items','pm_tasks']:
    try:
        cols=[r[1] for r in cur.execute(f\"PRAGMA table_info({t});\").fetchall()]
        print(f'{t} cols:', cols)
    except Exception as e:
        print(f'{t} check error:', e)
conn.close()
"@
    $tempCheck = Join-Path $migrationsDir "post_check.py"
    $checkCmd | Out-File -FilePath $tempCheck -Encoding UTF8 -Force
    & $pythonExe $tempCheck
} catch {
    Write-Host "[WARN] Post-check failed: $_" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Migration script finished. If you need to revert, restore the backup file created earlier." -ForegroundColor Cyan
Write-Host ""
