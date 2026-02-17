from datetime import datetime
from app.tasks.database import SessionLocal
from app.shop.service import QuestTemplateService
from app.shop.schemas import QuestTemplateCreate

s = SessionLocal()
try:
    data = QuestTemplateCreate(
        title='Тестовый шаблон',
        author='Tester',
        description='Описание',
        cost=10,
        rarity='Обычный',
        recurrence_type='daily',
        duration_hours=24,
        start_date=datetime.now().date().isoformat(),
        start_time='00:00',
        end_date='2026-05-24',
        end_time='23:59',
        is_active=True
    )
    tpl = QuestTemplateService.create_template(s, user_id=1, template_data=data)
    print('Created template id=', tpl.id, 'start_at=', tpl.start_at, 'end_at=', tpl.end_at)
finally:
    s.close()
