import sqlite3, json, os

DB='quests.db'
out='scripts/users_schema_output.json'
res={'db':DB}

try:
    conn=sqlite3.connect(DB)
    cur=conn.cursor()
    rows=cur.execute("PRAGMA table_info('users')").fetchall()
    res['rows']=rows
    res['cols']=[r[1] for r in rows]
    conn.close()
except Exception as e:
    res['error']=str(e)

with open(out,'w',encoding='utf-8') as f:
    json.dump(res,f,ensure_ascii=False,indent=2)
print('WROTE',out)
