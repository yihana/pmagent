import os, sqlite3, sys
p = "history.db"
print("DB:", os.path.abspath(p))
if not os.path.exists(p):
    print("ERROR: DB not found:", p); sys.exit(1)
conn = sqlite3.connect(p)
c = conn.cursor()
print("Tables:", c.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall())
try:
    cols = [r[1] for r in c.execute("PRAGMA table_info(pm_documents);")]
    print("pm_documents cols:", cols)
except Exception as e:
    print("PRAGMA failed:", e)
conn.close()
