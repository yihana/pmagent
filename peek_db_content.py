import os, sqlite3, textwrap

p = "history.db"  # 현재 DB 파일
print("📂 DB Path:", os.path.abspath(p))

if not os.path.exists(p):
print("❌ DB 파일이 없습니다.")
raise SystemExit(1)

conn = sqlite3.connect(p)
c = conn.cursor()

# === 테이블 존재 확인 ===

tables = [t[0] for t in c.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()]
if "pm_action_items" not in tables:
print("⚠️ pm_action_items 테이블이 존재하지 않습니다.")
raise SystemExit(1)

# === 컬럼명 확인 ===

cols = [r[1] for r in c.execute("PRAGMA table_info(pm_action_items);")]
print(f"\n📑 Columns ({len(cols)}):", cols)

# === 데이터 내용 조회 ===

rows = c.execute("SELECT * FROM pm_action_items LIMIT 20;").fetchall()
if not rows:
print("⚠️ 데이터가 없습니다.")
else:
print(f"\n📊 Showing {len(rows)} rows (최대 20개):\n")
for idx, row in enumerate(rows, 1):
print(f"[{idx}]")
for col, val in zip(cols, row):
print(f"   {col}: {val}")
print("-" * 40)

conn.close()
