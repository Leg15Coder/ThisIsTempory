from pathlib import Path
import sqlite3
import os

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / 'quests.db'

if not DB.exists():
    print('БД не найдена по пути', DB)
    raise SystemExit(1)

conn = sqlite3.connect(str(DB))
cur = conn.cursor()

cur.execute("PRAGMA table_info(quests)")
cols = cur.fetchall()
col_names = [c[1] for c in cols]
print('Существующие колонки в quests:', col_names)
if 'user_id' in col_names:
    print('Колонка user_id уже присутствует, изменений не требуется')
    conn.close()
    raise SystemExit(0)

print('Добавляю колонку user_id в таблицу quests (ALTER TABLE)...')
cur.execute("ALTER TABLE quests ADD COLUMN user_id INTEGER;")
# create index for user_id
cur.execute("CREATE INDEX IF NOT EXISTS ix_quests_user_id ON quests (user_id);")

conn.commit()
conn.close()
print('Миграция завершена: колонка user_id добавлена.')
