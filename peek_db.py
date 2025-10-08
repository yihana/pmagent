import os, sqlite3

p = "history.db"
print("DB:", os.path.abspath(p))

conn = sqlite3.connect(p)
c = conn.cursor()

tables = c.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()
print("Tables:", tables)

if any(name == "pm_action_items" for (name,) in tables):
    cols = [r[1] for r in c.execute("PRAGMA table_info(pm_action_items);")]
    print("pm_action_items cols:", cols)
else:
    print("❌ pm_action_items 테이블이 없습니다.")
