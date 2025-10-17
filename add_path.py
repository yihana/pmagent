import os, sqlite3, sys
p = "history.db"
print("DB file:", os.path.abspath(p))
if not os.path.exists(p):
    print("ERROR: DB file not found:", p)
    sys.exit(1)

conn = sqlite3.connect(p)
c = conn.cursor()

# 테이블 존재 확인
c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='pm_documents';")
if not c.fetchone():
    print("ERROR: pm_documents 테이블이 없습니다. DB 스키마를 확인하세요.")
    conn.close()
    sys.exit(2)

# 컬럼 확인
cols = [r[1] for r in c.execute("PRAGMA table_info(pm_documents);")]
print("pm_documents cols (before):", cols)

# path 컬럼이 없는 경우 추가
if "path" not in cols:
    try:
        c.execute("ALTER TABLE pm_documents ADD COLUMN path TEXT;")
        conn.commit()
        print("✅ Added column 'path' to pm_documents.")
    except Exception as e:
        print("ERROR adding column 'path':", e)
        conn.rollback()
        conn.close()
        sys.exit(3)
else:
    print("Column 'path' already exists. Nothing to do.")

# 확인
cols_after = [r[1] for r in c.execute("PRAGMA table_info(pm_documents);")]
print("pm_documents cols (after):", cols_after)

conn.close()
