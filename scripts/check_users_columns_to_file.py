import sqlite3

DB='quests.db'
out='scripts/users_cols.txt'
conn=sqlite3.connect(DB)
cur=conn.cursor()
cols=[c[1] for c in cur.execute("PRAGMA table_info('users')").fetchall()]

with open(out,'w',encoding='utf-8') as f:
    f.write(','.join(cols))
conn.close()
print('WROTE',out)
