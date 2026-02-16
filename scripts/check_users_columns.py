import sqlite3

DB = 'quests.db'
conn = sqlite3.connect(DB)
cur = conn.cursor()
cols = [c[1] for c in cur.execute("PRAGMA table_info('users')").fetchall()]
print('users columns:', cols)
conn.close()
