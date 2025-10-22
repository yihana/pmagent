#!/usr/bin/env python3
# apply_full_migration.py
import sqlite3, sys, os
from pathlib import Path

def apply_sql(db_path: str, sql_path: str):
    conn = sqlite3.connect(db_path)
    try:
        with open(sql_path, "r", encoding="utf-8") as f:
            script = f.read()
        conn.executescript(script)
        conn.commit()
        print("[apply] SQL migration applied.")
    except Exception as e:
        conn.rollback()
        print("[apply][ERROR] applying SQL:", e)
        raise
    finally:
        conn.close()

def table_exists(conn, table):
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?;", (table,))
    return cur.fetchone() is not None

def pragma_columns(conn, table):
    cur = conn.cursor()
    try:
        cur.execute(f"PRAGMA table_info({table});")
        return [r[1] for r in cur.fetchall()]
    except Exception as e:
        print(f"[apply] PRAGMA failed for {table}: {e}")
        return []

def ensure_column(conn, table: str, column: str, coltype: str = "TEXT"):
    cols = pragma_columns(conn, table)
    if column in cols:
        print(f"[apply] Column '{column}' already exists in '{table}'.")
        return
    try:
        cur = conn.cursor()
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {coltype};")
        conn.commit()
        print(f"[apply] Added column '{column}' to '{table}'.")
    except Exception as e:
        conn.rollback()
        print(f"[apply][WARN] Could not add {column} to {table}: {e}")

def main(argv):
    if len(argv) < 3:
        print("Usage: apply_full_migration.py DB_PATH SQL_PATH")
        return 2
    db_path = Path(argv[1]).resolve()
    sql_path = Path(argv[2]).resolve()
    print("DB:", db_path)
    if not sql_path.exists():
        print("SQL file not found:", sql_path)
        return 3
    # ensure DB dir exists
    if not db_path.parent.exists():
        db_path.parent.mkdir(parents=True, exist_ok=True)
    # apply base SQL
    apply_sql(str(db_path), str(sql_path))
    # now check and ensure legacy columns
    conn = sqlite3.connect(str(db_path))
    try:
        # pm_documents.path TEXT
        if table_exists(conn, "pm_documents"):
            ensure_column(conn, "pm_documents", "path", "TEXT")
        else:
            print("[apply] Table pm_documents not present; skip adding path column.")

        # pm_action_items.meeting_id INTEGER
        if table_exists(conn, "pm_action_items"):
            ensure_column(conn, "pm_action_items", "meeting_id", "INTEGER")
        else:
            print("[apply] Table pm_action_items not present; skip adding meeting_id column.")

        # Other safety checks: ensure pm_tasks exists etc (we created them in SQL)
        for t in ["pm_tasks", "pm_scope", "pm_schedule", "pm_sprints", "pm_task_links", "pm_output_versions", "pm_logs"]:
            if not table_exists(conn, t):
                print(f"[apply][WARN] Expected table '{t}' not present after SQL apply.")
    finally:
        conn.close()

    print("[apply] Full migration finished.")
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main(sys.argv))
