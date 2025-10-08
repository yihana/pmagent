import os, sqlite3
from sqlalchemy.orm import configure_mappers

# 1) SQLAlchemy 엔진/베이스
from server.db.database import Base, engine

# 2) 모델 등록 (⭐ 중요: 반드시 import 해야 테이블이 등록됩니다)
import server.db.pm_models  # noqa

print("Engine:", engine)

# 3) 매퍼 구성 강제
configure_mappers()

# 4) 기존 파일 삭제 (있다면)
db_path = "history8.db"
if os.path.exists(db_path):
    os.remove(db_path)
    print("Removed old DB:", os.path.abspath(db_path))

# 5) 스키마 생성
Base.metadata.create_all(bind=engine)
print("Created schema.")

# 6) 생성 검증
conn = sqlite3.connect(db_path)
c = conn.cursor()
tables = c.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()
print("Tables:", tables)

def cols(t):
    return [r[1] for r in c.execute(f"PRAGMA table_info({t});")]

for (tname,) in tables:
    print(f"[{tname}] cols:", cols(tname))

# pm_action_items에 meeting_id 있는지 확인
pm_ai_cols = [r[1] for r in c.execute("PRAGMA table_info(pm_action_items);")]
print("pm_action_items has meeting_id?:", "meeting_id" in pm_ai_cols)
