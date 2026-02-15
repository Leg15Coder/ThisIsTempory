import os
import sqlite3
from urllib.parse import urlparse
from app.tasks import database

DB_URL = os.environ.get('DATABASE_URL') or 'sqlite:///./quests.db'
print('Используется DATABASE_URL =', DB_URL)

parsed = urlparse(DB_URL)

if parsed.scheme in ('', 'sqlite') or DB_URL.startswith('sqlite'):
    if DB_URL.startswith('sqlite:///'):
        db_path = DB_URL.replace('sqlite:///', '')
    elif DB_URL.startswith('sqlite://'):
        db_path = DB_URL.replace('sqlite://', '')
    else:
        db_path = '../../quests.db'

    db_path = os.path.abspath(db_path)
    print('Обнаружен путь к SQLite БД:', db_path)

    if not os.path.exists(db_path):
        print('❌ SQLite база не найдена по пути', db_path)
        raise SystemExit(1)

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='refresh_tokens'")
    if not cur.fetchone():
        print('❌ Таблица refresh_tokens не найдена. Нечего менять.')
        conn.close()
        raise SystemExit(1)

    try:
        cur.execute("PRAGMA foreign_key_list('refresh_tokens')")
        fk = cur.fetchall()
        if fk:
            print('✅ FOREIGN KEY уже присутствует в refresh_tokens:', fk)
            conn.close()
            raise SystemExit(0)
    except Exception:
        pass

    print('🔄 Создаю новую таблицу refresh_tokens_new с FOREIGN KEY и копирую данные...')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS refresh_tokens_new (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            token TEXT UNIQUE,
            expires_at TEXT NOT NULL,
            created_at TEXT,
            is_revoked INTEGER DEFAULT 0,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
    ''')

    cur.execute("PRAGMA table_info(refresh_tokens)")
    cols = [r[1] for r in cur.fetchall()]
    cols_str = ','.join(cols)

    try:
        cur.execute(f"INSERT INTO refresh_tokens_new ({cols_str}) SELECT {cols_str} FROM refresh_tokens;")
    except Exception as e:
        print('⚠️ Не удалось автоматически скопировать все данные:', e)
        print('   Проверьте данные в refresh_tokens и заполните user_id перед миграцией.')

    cur.execute("ALTER TABLE refresh_tokens RENAME TO refresh_tokens_old;")
    cur.execute("ALTER TABLE refresh_tokens_new RENAME TO refresh_tokens;")

    conn.commit()
    conn.close()

    print('✅ Миграция для SQLite завершена. Старую таблицу сохранено как refresh_tokens_old.')
    print('Если что-то пошло не так, откатите, восстановив старую таблицу из refresh_tokens_old.')

else:
    print('Обнаружена не-sqlite БД. Выполните в вашей СУБД:')
    print()
    print('ALTER TABLE refresh_tokens')
    print('ADD CONSTRAINT fk_refresh_user FOREIGN KEY (user_id) REFERENCES users(id);')
    print()
    print('После этого перезапустите приложение.')

print('Готово.')
