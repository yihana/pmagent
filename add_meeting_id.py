import os, sqlite3
p = "history.db"  # ← 지금 엔진이 바라보는 DB
print("DB:", os.path.abspath(p))
conn = sqlite3.connect(p)
c = conn.cursor()

# 현재 컬럼 확인
cols = [r[1] for r in c.execute("PRAGMA table_info(pm_action_items);")]
print("pm_action_items cols(before):", cols)

# meeting_id 없으면 추가 (FK 제약은 SQLite 특성상 즉시 추가 어려우므로 컬럼만 추가)
if "meeting_id" not in cols:
    c.execute("ALTER TABLE pm_action_items ADD COLUMN meeting_id INTEGER")
    print("✅ added column meeting_id")

conn.commit()

# 확인
cols = [r[1] for r in c.execute("PRAGMA table_info(pm_action_items);")]
print("pm_action_items cols(after):", cols)
