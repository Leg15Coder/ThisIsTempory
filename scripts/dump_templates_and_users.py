import sqlite3, json
DB='quests.db'
conn=sqlite3.connect(DB)
cur=conn.cursor()

users = cur.execute("SELECT id,email,created_at FROM users LIMIT 5").fetchall()
templates = cur.execute("SELECT id,user_id,title,start_at,end_at FROM quest_templates ORDER BY id DESC LIMIT 10").fetchall()
res={'users':users,'templates':templates}
print(json.dumps(res, ensure_ascii=False, indent=2))
conn.close()
