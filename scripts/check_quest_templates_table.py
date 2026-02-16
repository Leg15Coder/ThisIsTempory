import sqlite3

conn=sqlite3.connect('quests.db')
cur=conn.cursor()
cols = cur.execute("PRAGMA table_info('quest_templates')").fetchall()
print('COLUMNS:', cols)
rows = cur.execute("SELECT id, user_id, title, start_at, end_at, last_generated FROM quest_templates ORDER BY id DESC LIMIT 20").fetchall()
print('ROWS:', rows)
conn.close()
