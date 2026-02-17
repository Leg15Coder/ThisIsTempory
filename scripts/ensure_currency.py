import sqlite3

DB='quests.db'
print('DB path:', DB)
conn=sqlite3.connect(DB)
cur=conn.cursor()

try:
    cols=[c[1] for c in cur.execute("PRAGMA table_info('users')").fetchall()]
    print('Before:', cols)
except Exception as e:
    print('PRAGMA error:', e)

if 'currency' not in cols:
    try:
        cur.execute("ALTER TABLE users ADD COLUMN currency INTEGER DEFAULT 0")
        conn.commit()
        print('Added currency column')
    except Exception as e:
        print('Error adding column:', e)
else:
    print('currency already present')

cols2=[c[1] for c in cur.execute("PRAGMA table_info('users')").fetchall()]
print('After:', cols2)
conn.close()
