import sqlite3, json

conn = sqlite3.connect('quests.db')
cur = conn.cursor()
rows = cur.execute("PRAGMA table_info('quests')").fetchall()
print('Колонки таблицы quests:')
print(json.dumps(rows, ensure_ascii=False, indent=2))
conn.close()
