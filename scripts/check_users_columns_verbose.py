import sqlite3, sys, os

DB = os.path.join(os.getcwd(), 'quests.db')
print('DB path:', DB)
conn = sqlite3.connect(DB)
cur = conn.cursor()
rows = cur.execute("PRAGMA table_info('users')").fetchall()
print('raw rows:', rows)
cols = [c[1] for c in rows]
print('users columns:', cols)
conn.close()
sys.stdout.flush()
