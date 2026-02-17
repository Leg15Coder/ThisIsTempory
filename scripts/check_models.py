import traceback
from app.tasks import database

print('URL подключения к БД (engine):', database.engine.url)

try:
    import app.auth.models
    print('Модуль app.auth.models импортирован успешно')
except Exception:
    print('Исключение при импорте app.auth.models:')
    traceback.print_exc()

print('\nЗарегистрированные таблицы в Base.metadata:')
for name in sorted(database.Base.metadata.tables.keys()):
    print(' -', name)

import sqlite3, os
db_path = './quests.db'
print('\nФайл БД существует:', os.path.exists(db_path))
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    rows = cur.fetchall()
    print('Таблицы в sqlite файле:')
    for r in rows:
        print(' -', r[0])
    conn.close()
else:
    print('SQLite файл не найден по', db_path)
