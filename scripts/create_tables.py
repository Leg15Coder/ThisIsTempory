import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

print('Корневая папка проекта:', ROOT)

try:
    from app.tasks.database import Base, engine
    import importlib
    importlib.import_module('app.auth.models')
except Exception as e:
    print(f'Ошибка импорта моделей при выполнении скрипта: {e}')
    raise

print('Создаю таблицы...')
Base.metadata.create_all(bind=engine)
print('Таблицы созданы (или уже имеются в БД)')

import sqlite3
DB_PATH = ROOT / 'quests.db'
print('Путь к БД:', DB_PATH)
if DB_PATH.exists():
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    rows = cur.fetchall()
    print('Список таблиц:')
    for r in rows:
        print(' -', r[0])
    conn.close()
else:
    print('Файл sqlite БД не найден по адресу', DB_PATH)
