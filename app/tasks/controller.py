import time
from datetime import datetime, timedelta as td

from sqlalchemy import or_, case

from app.core.database import get_db
from app.tasks.database import QuestStatus, QuestRarity, Quest, QuestGenerator


async def flex_quest_filter(quests, sort_type: str, find: str):
    if find is not None:
        search = f"%{find}%"
        quests = quests.filter(
            or_(
                Quest.title.ilike(search),
                Quest.author.ilike(search),
                Quest.description.ilike(search),
                Quest.rarity.ilike(search),
                Quest.status.ilike(search),
            )
        )

        try:
            date_search = datetime.strptime(find, "%Y-%m-%d").date()
            quests = quests.filter(
                or_(
                    Quest.deadline == date_search,
                    Quest.created == date_search,
                )
            )
        except ValueError:
            pass

    if sort_type is not None:
        sort_atr, sort_order = sort_type.split('-')
        is_asc = sort_order != 'desc'
        if sort_atr in ('created', 'deadline', 'title'):
            sort_column = getattr(Quest, sort_atr)
            quests = quests.order_by(sort_column.asc() if is_asc else sort_column.desc())
        elif sort_atr == 'rarity':
            order_expr = case(
                {
                    QuestRarity.common: 1,
                    "Обычный": 1,
                    QuestRarity.uncommon: 2,
                    "Необычный": 2,
                    QuestRarity.rare: 3,
                    "Редкий": 3,
                    QuestRarity.epic: 4,
                    "Эпический": 4,
                    QuestRarity.legendary: 5,
                    "Легендарный": 5
                },
                value=Quest.rarity,
                else_=-1,
            )
            quests = quests.order_by(order_expr.asc() if is_asc else order_expr.desc())
    return quests.all()


async def choose_todays(db):
    failed = db.query(Quest).filter(Quest.status == QuestStatus.active).filter(Quest.deadline < datetime.now()).all()
    for quest in failed:
        quest.status = QuestStatus.failed
    db.commit()

    todays = (db.query(Quest).filter(
        Quest.status == QuestStatus.active,
        or_(
            Quest.scope == None,
            Quest.scope.notin_(["today", f"not_today_{datetime.now().date()}"])
        ),
        Quest.deadline <= datetime.now() + td(days=2))
    ).all()

    return todays


def update_generators():
    while True:
        with next(get_db()) as db:
            generators = db.query(QuestGenerator).all()

            for generator in generators:
                if generator.last_generate + generator.period > datetime.now():
                    generator.generate_quest()

        time.sleep(60)
