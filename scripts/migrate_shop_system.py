import sqlite3
import os
from datetime import datetime

DB_PATH = 'quests.db'
BACKUP_PATH = 'quests.db.bak'

if not os.path.exists(DB_PATH):
    print(f"БД {DB_PATH} не найдена. Отмена миграции.")
    raise SystemExit(1)

if not os.path.exists(BACKUP_PATH):
    import shutil
    shutil.copy2(DB_PATH, BACKUP_PATH)
    print(f"Резервная копия создана: {BACKUP_PATH}")
else:
    print(f"Резервная копия уже существует: {BACKUP_PATH}")

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cols = [c[1] for c in cur.execute("PRAGMA table_info('users')").fetchall()]
if 'currency' not in cols:
    try:
        print('Добавляю колонку currency в users...')
        cur.execute("ALTER TABLE users ADD COLUMN currency INTEGER DEFAULT 0")
        conn.commit()
        print('Колонка currency добавлена')
    except Exception as e:
        print('Ошибка при добавлении currency:', e)
else:
    print('Колонка currency уже существует')

cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='shop_items'")
if not cur.fetchone():
    print('Создаю таблицу shop_items...')
    cur.execute('''
        CREATE TABLE shop_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            price INTEGER NOT NULL,
            rarity TEXT DEFAULT 'Обычный',
            icon TEXT,
            is_available INTEGER DEFAULT 1,
            stock INTEGER,
            created_at TEXT DEFAULT (datetime('now'))
        );
    ''')
    cur.execute("CREATE INDEX IF NOT EXISTS ix_shop_items_user_id ON shop_items (user_id);")
    conn.commit()
    print('shop_items создана')
else:
    print('shop_items уже существует')

cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='inventory'")
if not cur.fetchone():
    print('Создаю таблицу inventory...')
    cur.execute('''
        CREATE TABLE inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            shop_item_id INTEGER NOT NULL,
            quantity INTEGER DEFAULT 1,
            used_quantity INTEGER DEFAULT 0,
            purchased_at TEXT DEFAULT (datetime('now')),
            last_used TEXT
        );
    ''')
    cur.execute("CREATE INDEX IF NOT EXISTS ix_inventory_user_id ON inventory (user_id);")
    conn.commit()
    print('inventory создана')
else:
    print('inventory уже существует')

cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='quest_templates'")
if not cur.fetchone():
    print('Создаю таблицу quest_templates...')
    cur.execute('''
        CREATE TABLE quest_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            author TEXT DEFAULT '???',
            description TEXT,
            cost INTEGER NOT NULL,
            rarity TEXT DEFAULT 'Обычный',
            scope TEXT,
            recurrence_type TEXT NOT NULL,
            duration_hours INTEGER NOT NULL DEFAULT 24,
            weekdays TEXT,
            interval_hours INTEGER,
            is_active INTEGER DEFAULT 1,
            last_generated TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
    ''')
    cur.execute("CREATE INDEX IF NOT EXISTS ix_quest_templates_user_id ON quest_templates (user_id);")
    conn.commit()
    print('quest_templates создана')
else:
    print('quest_templates уже существует')

conn.close()
print('\nМиграция завершена.')
