from datetime import datetime, timedelta as td

from sqlalchemy import or_, case
from app.database import QuestStatus, QuestRarity, Quest


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
            exec(f'quests = quests.order_by(Quest.{sort_atr}.asc() if is_asc else Quest.{sort_atr}.desc())')
        elif sort_atr == 'rarity':
            order_expr = case(
                {
                    QuestRarity.common: 1,
                    QuestRarity.uncommon: 2,
                    QuestRarity.rare: 3,
                    QuestRarity.epic: 4,
                    QuestRarity.legendary: 5,
                },
                value=Quest.rarity
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
