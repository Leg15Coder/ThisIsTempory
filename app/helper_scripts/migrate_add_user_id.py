import sqlite3
import os
from datetime import datetime

DB_PATH = "../../quests.db"


def migrate():
    """Добавляет столбец user_id в таблицу quests"""
    if not os.path.exists(DB_PATH):
        print(f"❌ База данных {DB_PATH} не найдена")
        raise SystemExit(1)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("PRAGMA table_info(quests)")
    cols = [column[1] for column in cur.fetchall()]

    if 'user_id' in cols:
        print('✅ Столбец user_id уже существует')
        raise SystemExit(0)

    print('🔄 Добавляю столбец user_id в таблицу quests...')

    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
    if not cur.fetchone():
        print('❌ Таблица users не найдена. Создайте пользователей через /auth/register')
        conn.close()
        raise SystemExit(1)

    cur.execute('SELECT COUNT(*) FROM users')
    count = cur.fetchone()[0]
    if count == 0:
        print('⚠️ Пользователи не найдены. Создаю тестового пользователя...')
        cur.execute("INSERT INTO users (email, username, display_name, hashed_password, is_active, is_verified) VALUES ('test@example.com','test','Test User','',1,1)")
        conn.commit()

    cur.execute('SELECT id FROM users LIMIT 1')
    user_id = cur.fetchone()[0]
    print(f'👤 Используем пользователя ID: {user_id}')

    cur.execute('ALTER TABLE quests ADD COLUMN user_id INTEGER;')
    cur.execute('UPDATE quests SET user_id = ? WHERE user_id IS NULL', (user_id,))
    cur.execute('CREATE INDEX IF NOT EXISTS ix_quests_user_id ON quests (user_id);')
    conn.commit()
    conn.close()

    print('✅ Миграция успешно выполнена!')
    print(f'   Все существующие квесты привязаны к пользователю ID: {user_id}')


if __name__ == "__main__":
    print("=" * 50)
    print("Миграция: Добавление user_id к квестам")
    print("=" * 50)
    migrate()
    print("\n💡 Теперь все квесты требуют авторизации пользователя")
    print("   Зарегистрируйтесь на /auth/register или войдите на /auth/login")
