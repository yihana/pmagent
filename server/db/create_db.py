#!/usr/bin/env python3
"""
server/db/create_db.py

사용법:
  # 기본: 존재하지 않는 테이블을 생성
  python server/db/create_db.py

  # 강제로 기존 테이블 모두 삭제 후 재생성 (데이터 삭제됨)
  python server/db/create_db.py --drop

  # DB 파일(또는 DB 연결 문자열)을 백업한 뒤 실행
  python server/db/create_db.py --backup

  # 백업시 파일명 지정 (예: --backup-file backup.db)
  python server/db/create_db.py --backup --backup-file history.bak.db
"""

import argparse
import shutil
import sys
import os
from pathlib import Path

# 임포트 시 server.db.session 에서 engine, Base를 얻도록 프로젝트 구조를 따릅니다.
try:
    from server.db.session import engine, Base
except Exception as e:
    print("ERROR: cannot import server.db.session (engine/Base).")
    print("Detail:", e)
    sys.exit(1)


def detect_sqlite_file_from_engine(engine):
    """
    SQLAlchemy engine에서 sqlite 파일 경로를 추출하려 시도합니다.
    Returns None if not sqlite or cannot detect.
    """
    try:
        url = engine.url
        # url.drivername 예: 'sqlite', 'postgresql', 'mysql+pymysql'
        if url.drivername.startswith("sqlite"):
            # For sqlite, 'database' property is file path or ':memory:'
            db_path = url.database
            return db_path
    except Exception:
        pass
    return None


def backup_sqlite_file(sqlite_path: str, backup_file: str = None):
    p = Path(sqlite_path)
    if not p.exists():
        raise FileNotFoundError(f"DB file not found: {sqlite_path}")
    if backup_file is None:
        backup_file = str(p.with_suffix(p.suffix + ".bak"))
    shutil.copy2(str(p), str(backup_file))
    return backup_file


def main():
    ap = argparse.ArgumentParser(description="Create (or recreate) DB tables from SQLAlchemy metadata.")
    ap.add_argument("--drop", action="store_true", help="Drop all tables before creating (irreversible).")
    ap.add_argument("--backup", action="store_true", help="Backup sqlite DB file if applicable before changes.")
    ap.add_argument("--backup-file", type=str, default=None, help="Optional backup file path.")
    ap.add_argument("--verbose", "-v", action="store_true", help="Verbose output.")
    args = ap.parse_args()

    # Ensure models are imported so they are registered on Base.metadata.
    # Users should ensure server/db/pm_models.py (and other model modules) import here.
    # Try to import common model modules (best-effort, ignore failures but warn)
    model_modules = [
        "server.db.pm_models",
        "server.db.models",
        #"server.db.legacy_models",
        #"server.db.pm_models_extra",  # optional extra
    ]
    for m in model_modules:
        try:
            __import__(m)
            if args.verbose:
                print(f"Imported models module: {m}")
        except ModuleNotFoundError:
            # it's okay if optional modules are missing
            if args.verbose:
                print(f"Model module not found (skipping): {m}")
        except Exception as e:
            print(f"Warning: failed importing {m}: {e}")

    # Optional backup for sqlite
    if args.backup:
        sqlite_file = detect_sqlite_file_from_engine(engine)
        if sqlite_file:
            try:
                backup_target = args.backup_file or None
                backup_path = backup_sqlite_file(sqlite_file, backup_target)
                print(f"Backed up sqlite DB file: {sqlite_file} -> {backup_path}")
            except Exception as e:
                print("ERROR during backup:", e)
                sys.exit(2)
        else:
            print("Backup requested but underlying DB is not SQLite (or path not detectable). Skipping file backup.")

    # If drop requested: drop all tables first (warning)
    if args.drop:
        confirm = "y"
        # If run interactively, ask for confirmation
        try:
            if sys.stdin.isatty():
                confirm = input("DROP all tables? This will DELETE ALL DATA. Type 'yes' to continue: ")
        except Exception:
            pass
        if confirm.lower() not in ("y", "yes"):
            print("Drop aborted by user.")
            sys.exit(0)
        print("Dropping all tables...")
        Base.metadata.drop_all(bind=engine)
        print("Dropped all tables.")

    # Create tables from metadata
    print("Creating tables from SQLAlchemy metadata...")
    try:
        Base.metadata.create_all(bind=engine)
        print("Done. Tables created (if missing).")
    except Exception as e:
        print("ERROR: Failed to create tables:", e)
        sys.exit(3)


if __name__ == "__main__":
    main()
