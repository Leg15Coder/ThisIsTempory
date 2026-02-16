import sqlite3, json, os

DB='quests.db'
out='scripts/users_cols_report.json'
result={'db':DB,'before':None,'after':None,'added':False,'error':None}

try:
    conn=sqlite3.connect(DB)
    cur=conn.cursor()
    rows=cur.execute("PRAGMA table_info('users')").fetchall()
    cols=[c[1] for c in rows]
    result['before']=cols
    if 'currency' not in cols:
        try:
            cur.execute("ALTER TABLE users ADD COLUMN currency INTEGER DEFAULT 0")
            conn.commit()
            result['added']=True
        except Exception as e:
            result['error']=str(e)
    rows2=cur.execute("PRAGMA table_info('users')").fetchall()
    cols2=[c[1] for c in rows2]
    result['after']=cols2
    conn.close()
except Exception as e:
    result['error']=str(e)

with open(out,'w',encoding='utf-8') as f:
    json.dump(result,f,ensure_ascii=False,indent=2)
print('WROTE',out)
