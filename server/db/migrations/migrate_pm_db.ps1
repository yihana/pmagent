# migrate_pm_db.ps1
# PMP 표준 산출물 지원을 위한 DB 마이그레이션 스크립트
#
# 사용법:
#   .\migrate_pm_db.ps1
#   .\migrate_pm_db.ps1 -DBPath "custom_path.db"

param(
    [string]$DBPath = "pm_agent.db",
    [switch]$Force = $false
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "PM Agent DB Migration Script" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 1. 현재 디렉토리 확인
$CurrentDir = Get-Location
Write-Host "[INFO] Current Directory: $CurrentDir" -ForegroundColor Yellow

# 2. DB 파일 경로 설정
if (-not [System.IO.Path]::IsPathRooted($DBPath)) {
    $DBPath = Join-Path $CurrentDir $DBPath
}

Write-Host "[INFO] DB Path: $DBPath" -ForegroundColor Yellow

# 3. DB 파일 존재 확인
if (-not (Test-Path $DBPath)) {
    if ($Force) {
        Write-Host "[WARN] DB file not found. Creating new database..." -ForegroundColor Yellow
    } else {
        Write-Host "[ERROR] DB file not found: $DBPath" -ForegroundColor Red
        Write-Host "[INFO] Use -Force flag to create new database" -ForegroundColor Yellow
        exit 1
    }
} else {
    Write-Host "[OK] DB file found" -ForegroundColor Green
}

# 4. SQL 파일 경로 확인
$SQLFile = Join-Path $CurrentDir "server\db\migrations\add_pmp_outputs.sql"

if (-not (Test-Path $SQLFile)) {
    Write-Host "[ERROR] SQL migration file not found: $SQLFile" -ForegroundColor Red
    exit 1
}

Write-Host "[OK] SQL file found: $SQLFile" -ForegroundColor Green

# 5. 백업 생성
$BackupPath = "$DBPath.backup_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
Write-Host ""
Write-Host "[INFO] Creating backup..." -ForegroundColor Yellow

try {
    if (Test-Path $DBPath) {
        Copy-Item $DBPath $BackupPath -Force
        Write-Host "[OK] Backup created: $BackupPath" -ForegroundColor Green
    }
} catch {
    Write-Host "[WARN] Backup failed: $_" -ForegroundColor Yellow
    Write-Host "[INFO] Continuing without backup..." -ForegroundColor Yellow
}

# 6. Python 스크립트 생성 (임시)
$PythonScript = @"
import sqlite3
import sys
from pathlib import Path

db_path = r'$DBPath'
sql_path = r'$SQLFile'

print(f'[INFO] Connecting to database: {db_path}')

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print('[INFO] Reading SQL file...')
    with open(sql_path, 'r', encoding='utf-8') as f:
        sql_script = f.read()
    
    print('[INFO] Executing migration...')
    
    # SQLite에서는 ALTER TABLE ADD COLUMN이 이미 존재하는 컬럼에 대해 실패할 수 있으므로
    # 각 명령을 개별적으로 실행하고 에러를 무시
    statements = sql_script.split(';')
    
    success_count = 0
    skip_count = 0
    
    for statement in statements:
        statement = statement.strip()
        if not statement or statement.startswith('--'):
            continue
        
        try:
            cursor.execute(statement)
            success_count += 1
        except sqlite3.OperationalError as e:
            if 'duplicate column name' in str(e).lower() or 'already exists' in str(e).lower():
                skip_count += 1
                print(f'[SKIP] {str(e)}')
            else:
                raise
    
    conn.commit()
    print(f'[OK] Migration completed: {success_count} statements executed, {skip_count} skipped')
    
    # 테이블 목록 확인
    print('')
    print('[INFO] Verifying tables...')
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = cursor.fetchall()
    
    print('[OK] Tables in database:')
    for table in tables:
        print(f'  - {table[0]}')
    
    conn.close()
    print('')
    print('[SUCCESS] Migration completed successfully!')
    sys.exit(0)
    
except Exception as e:
    print(f'[ERROR] Migration failed: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)
"@

$TempPyFile = Join-Path $env:TEMP "migrate_pm_db_temp.py"
$PythonScript | Out-File -FilePath $TempPyFile -Encoding UTF8

Write-Host ""
Write-Host "[INFO] Running migration..." -ForegroundColor Yellow

# 7. Python 실행
try {
    $result = python $TempPyFile 2>&1
    Write-Host $result
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host ""
        Write-Host "========================================" -ForegroundColor Green
        Write-Host "Migration completed successfully!" -ForegroundColor Green
        Write-Host "========================================" -ForegroundColor Green
        Write-Host ""
        Write-Host "[INFO] Backup location: $BackupPath" -ForegroundColor Cyan
        Write-Host "[INFO] You can now use PMP standard outputs" -ForegroundColor Cyan
    } else {
        Write-Host ""
        Write-Host "========================================" -ForegroundColor Red
        Write-Host "Migration failed!" -ForegroundColor Red
        Write-Host "========================================" -ForegroundColor Red
        Write-Host ""
        Write-Host "[INFO] Restoring from backup..." -ForegroundColor Yellow
        
        if (Test-Path $BackupPath) {
            Copy-Item $BackupPath $DBPath -Force
            Write-Host "[OK] Database restored from backup" -ForegroundColor Green
        }
        exit 1
    }
} catch {
    Write-Host "[ERROR] Python execution failed: $_" -ForegroundColor Red
    Write-Host "[INFO] Make sure Python is installed and in PATH" -ForegroundColor Yellow
    exit 1
} finally {
    # 임시 파일 삭제
    if (Test-Path $TempPyFile) {
        Remove-Item $TempPyFile -Force
    }
}

Write-Host ""
Write-Host "[TIP] To rollback, use: Copy-Item '$BackupPath' '$DBPath' -Force" -ForegroundColor Cyan
Write-Host ""