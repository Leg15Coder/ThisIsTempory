import sys
import os
# Добавляем корневую папку проекта в sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.tasks.schemas import QuestCreate

candidates = ['common', 'Обычный', 'rare', 'Редкий', 'epic', 'Эпический', 'invalid']
for val in candidates:
    try:
        q = QuestCreate(title='t', author='a', description='', rarity=val, cost=10)
        print(f"{val!r} -> {q.rarity} (type: {type(q.rarity)})")
    except Exception as e:
        print(f"{val!r} failed: {e}")
