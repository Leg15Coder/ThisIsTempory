from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import or_, case

from app.tasks.database import (
    Quest, QuestStatus, QuestRarity, CheckboxSubtask,
    NumericSubtask, QuestGenerator
)
from app.tasks.firestore_service import (
    list_quests as fs_list_quests,
    get_quest as fs_get_quest,
    create_quest as fs_create_quest,
    update_quest as fs_update_quest,
    delete_quest as fs_delete_quest
)

class QuestService:
    """Сервис для работы с квестами"""

    def __init__(self, db: Session, user_id: Optional[int] = None):
        self.db = db
        self.user_id = user_id

    def _get_user_filter(self):
        """Возвращает фильтр для квестов текущего пользователя"""
        if self.user_id is None:
            return Quest.id.is_(None)
        return Quest.user_id == self.user_id

    def get_quest_by_id(self, quest_id: int) -> Optional[Quest]:
        """Получить квест по ID (только для текущего пользователя)"""
        if self.db is None:
            return fs_get_quest(quest_id)
        return self.db.query(Quest).filter(
            Quest.id == quest_id,
            self._get_user_filter()
        ).first()

    def get_active_quests(self) -> list[type[Quest]]:
        """Получить все активные квесты текущего пользователя"""
        if self.db is None:
            return fs_list_quests(str(self.user_id), status='active')
        return self.db.query(Quest).filter(
            Quest.status == QuestStatus.active,
            self._get_user_filter()
        ).all()

    def get_archived_quests(self) -> list[type[Quest]]:
        """Получить все архивные квесты текущего пользователя"""
        if self.db is None:
            all_q = fs_list_quests(str(self.user_id))
            return [q for q in all_q if q.status != 'active']
        return self.db.query(Quest).filter(
            Quest.status != QuestStatus.active,
            self._get_user_filter()
        ).all()

    def get_all_quests(self) -> list[type[Quest]]:
        """Получить все квесты текущего пользователя"""
        if self.db is None:
            return fs_list_quests(str(self.user_id))
        return self.db.query(Quest).filter(self._get_user_filter()).all()

    def create_quest(
        self,
        title: str,
        rarity: QuestRarity,
        cost: int,
        author: str = "???",
        description: str = "",
        deadline: Optional[datetime] = None,
        parent_ids: Optional[List[int]] = None,
        subtasks_data: Optional[List[Dict[str, Any]]] = None
    ) -> Quest:
        """Создать новый квест для текущего пользователя"""
        if self.user_id is None:
            raise ValueError("User ID is required to create a quest")

        if self.db is None:
            payload = {
                'title': title,
                'author': author,
                'description': description,
                'deadline': deadline.isoformat() if deadline else None,
                'created': datetime.now().isoformat(),
                'rarity': rarity.value if hasattr(rarity, 'value') else str(rarity),
                'cost': cost,
                'parents': parent_ids or [],
                'subtasks': subtasks_data or [],
                'status': 'active'
            }
            return fs_create_quest(str(self.user_id), payload)

        quest = Quest(
            title=title,
            author=author,
            description=description,
            deadline=deadline,
            created=datetime.now(),
            rarity=rarity,
            cost=cost,
            user_id=self.user_id
        )
        self.db.add(quest)
        self.db.flush()

        if parent_ids:
            parents = self.db.query(Quest).filter(
                Quest.id.in_(parent_ids),
                self._get_user_filter()
            ).all()
            quest.parents.extend(parents)

            # Если все родители завершены - квест активен
            if all(p.status == QuestStatus.finished for p in parents):
                quest.status = QuestStatus.active
            else:
                quest.status = QuestStatus.inactive
        else:
            quest.status = QuestStatus.active

        if subtasks_data:
            self._create_subtasks(quest.id, subtasks_data)

        self.db.commit()
        return quest

    def _create_subtasks(self, quest_id: int, subtasks_data: List[Dict[str, Any]]):
        """Создать подзадачи для квеста"""
        if self.db is None:
            # Firestore mode: subtasks are saved inside quest document during create
            return
        for subtask_info in subtasks_data:
            if subtask_info['type'] == 'checkbox':
                subtask = CheckboxSubtask(
                    description=subtask_info['description'],
                    weight=subtask_info.get('weight', 1),
                    completed=subtask_info.get('completed', False),
                    quest_id=quest_id
                )
            elif subtask_info['type'] == 'numeric':
                subtask = NumericSubtask(
                    description=subtask_info['description'],
                    weight=subtask_info.get('weight', 1),
                    target=subtask_info['target'],
                    current=subtask_info.get('current', 0),
                    quest_id=quest_id
                )
            else:
                continue

            self.db.add(subtask)

    def mark_quest_read(self, quest_id: int) -> Optional[Quest]:
        """Отметить квест как прочитанный"""
        if self.db is None:
            q = fs_get_quest(quest_id)
            if q:
                # Firestore: set is_new false
                fs_update_quest(quest_id, {'is_new': False})
            return q
        quest = self.get_quest_by_id(quest_id)
        if quest:
            quest.is_new = False
            self.db.commit()
        return quest

    def complete_quest(self, quest_id: int) -> Optional[Quest]:
        """Завершить квест успешно"""
        if self.db is None:
            q = fs_get_quest(quest_id)
            if not q:
                return None
            fs_update_quest(quest_id, {'status': 'finished'})
            try:
                from app.tasks.firestore_service import update_user_currency
                # начислить стоимость квеста пользователю
                if getattr(q, 'user_id', None):
                    update_user_currency(str(q.user_id), int(getattr(q, 'cost', 0) or 0))
            except Exception:
                pass
            return fs_get_quest(quest_id)

        quest = self.get_quest_by_id(quest_id)
        if quest:
            quest.status = QuestStatus.finished
            self._update_children_status(quest)

            if quest.user:
                quest.user.currency += quest.cost

            self.db.commit()
        return quest

    def fail_quest(self, quest_id: int) -> Optional[Quest]:
        """Провалить квест"""
        if self.db is None:
            q = fs_get_quest(quest_id)
            if not q:
                return None
            fs_update_quest(quest_id, {'status': 'failed'})
            return fs_get_quest(quest_id)

        quest = self.get_quest_by_id(quest_id)
        if quest:
            quest.status = QuestStatus.failed
            self._update_children_status(quest)
            self.db.commit()
        return quest

    def return_to_active(self, quest_id: int) -> Optional[Quest]:
        """Вернуть квест в активное состояние"""
        if self.db is None:
            fs_update_quest(quest_id, {'status': 'active'})
            return fs_get_quest(quest_id)
        quest = self.get_quest_by_id(quest_id)
        if quest:
            quest.status = QuestStatus.active
            self._update_children_status(quest)
            self.db.commit()
        return quest

    def delete_quest(self, quest_id: int) -> bool:
        """Удалить квест"""
        if self.db is None:
            return fs_delete_quest(quest_id)
        quest = self.get_quest_by_id(quest_id)
        if quest:
            self.db.delete(quest)
            self.db.commit()
            return True
        return False

    @staticmethod
    def _update_children_status(quest: Quest):
        """Обновить статусы дочерних квестов"""
        for child in quest.children:
            if child.status == QuestStatus.inactive:
                if all(p.status == QuestStatus.finished for p in child.parents):
                    child.status = QuestStatus.active

    def set_quest_scope(self, quest_id: int, scope: str) -> Optional[Quest]:
        """Установить область видимости квеста (today/not_today)"""
        if self.db is None:
            fs_update_quest(quest_id, {'scope': scope})
            return fs_get_quest(quest_id)
        quest = self.get_quest_by_id(quest_id)
        if quest:
            quest.scope = scope
            self.db.commit()
        return quest

    @staticmethod
    def filter_quests(
            base_query,
        search: Optional[str] = None,
        sort_by: Optional[str] = None,
        sort_order: str = 'asc'
    ) -> List[Quest]:
        """Фильтрация и сортировка квестов"""
        query = base_query

        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                or_(
                    Quest.title.ilike(search_pattern),
                    Quest.author.ilike(search_pattern),
                    Quest.description.ilike(search_pattern),
                    Quest.rarity.ilike(search_pattern),
                    Quest.status.ilike(search_pattern),
                )
            )

            try:
                date_search = datetime.strptime(search, "%Y-%m-%d").date()
                query = query.filter(
                    or_(
                        Quest.deadline == date_search,
                        Quest.created == date_search,
                    )
                )
            except ValueError:
                pass

        if sort_by:
            is_asc = sort_order == 'asc'

            if sort_by in ('created', 'deadline', 'title', 'cost'):
                sort_column = getattr(Quest, sort_by)
                query = query.order_by(sort_column.asc() if is_asc else sort_column.desc())

            elif sort_by == 'rarity':
                order_expr = case(
                    {
                        QuestRarity.common: 1,
                        QuestRarity.uncommon: 2,
                        QuestRarity.rare: 3,
                        QuestRarity.epic: 4,
                        QuestRarity.legendary: 5
                    },
                    value=Quest.rarity,
                    else_=0,
                )
                query = query.order_by(order_expr.asc() if is_asc else order_expr.desc())

        return query.all()

    def get_todays_candidates(self) -> list[type[Quest]]:
        """Получить кандидатов на сегодняшние квесты"""
        if self.db is None:
            # Basic implementation: return active quests with deadline in near future
            all_q = fs_list_quests(str(self.user_id), status='active')
            now = datetime.now()
            candidates = [q for q in all_q if getattr(q, 'deadline', None) and q.deadline <= now + timedelta(days=2)]
            return candidates

        failed = self.db.query(Quest).filter(
            Quest.status == QuestStatus.active,
            Quest.deadline < datetime.now()
        ).all()

        for quest in failed:
            quest.status = QuestStatus.failed

        self.db.commit()

        today_candidates = self.db.query(Quest).filter(
            Quest.status == QuestStatus.active,
            or_(
                Quest.scope.is_(None),
                Quest.scope.notin_(["today", f"not_today_{datetime.now().date()}"])
            ),
            Quest.deadline <= datetime.now() + timedelta(days=2)
        ).all()

        return today_candidates

    def get_today_quests(self) -> list[type[Quest]]:
        """Получить квесты на сегодня"""
        if self.db is None:
            all_q = fs_list_quests(str(self.user_id), status='active')
            return [q for q in all_q if getattr(q, 'scope', None) == 'today']
        return (self.db.query(Quest)
                .filter(Quest.status == QuestStatus.active)
                .filter(Quest.scope == "today")
                .order_by(Quest.deadline.asc())
                .all())


class SubtaskService:
    """Сервис для работы с подзадачами"""

    def __init__(self, db: Session):
        self.db = db

    def update_checkbox_subtask(self, subtask_id: int, completed: bool) -> Optional[CheckboxSubtask]:
        """Обновить чекбокс подзадачу"""
        if self.db is None:
            # Firestore mode: not implemented
            return None
        subtask = self.db.query(CheckboxSubtask).filter(CheckboxSubtask.id == subtask_id).first()
        if subtask:
            subtask.completed = completed
            self.db.commit()
        return subtask

    def update_numeric_subtask(self, subtask_id: int, current: float) -> Optional[NumericSubtask]:
        """Обновить числовую подзадачу"""
        if self.db is None:
            # Firestore mode: not implemented
            return None
        subtask = self.db.query(NumericSubtask).filter(NumericSubtask.id == subtask_id).first()
        if subtask:
            subtask.current = current
            self.db.commit()
        return subtask

    def get_quest_progress(self, quest_id: int) -> Dict[str, Any]:
        """Получить прогресс квеста"""
        if self.db is None:
            q = fs_get_quest(quest_id)
            if not q:
                return {"progress": 0, "total": 0, "completed": 0}
            # naive progress calculation from subtasks
            subtasks = getattr(q, 'subtasks', [])
            total = 0
            completed = 0
            for s in subtasks:
                w = s.get('weight', 1)
                total += w
                if s.get('type') == 'checkbox' and s.get('completed'):
                    completed += w
                elif s.get('type') == 'numeric' and s.get('current', 0) >= s.get('target', 0):
                    completed += w
                else:
                    if s.get('type') == 'numeric':
                        completed += w * (s.get('current', 0) / max(1, s.get('target', 1)))
            prog = round((completed / total) * 100) if total > 0 else 0
            return {"progress": prog, "total": total, "completed": completed}
        quest = self.db.query(Quest).filter(Quest.id == quest_id).first()
        if not quest:
            return {"progress": 0, "total": 0, "completed": 0}

    @staticmethod
    def generate_due_quests(db: Session, user_id: int) -> List[Quest]:
         if db is None:
-            # Firestore mode: for simplicity, iterate templates and call create_quest
-            templates = fs_list_templates(user_id, active_only=True)
-            generated = []
-            now = datetime.now()
-            for t in templates:
-                try:
-                    # naive check if should generate using existing fields
-                    # if t has 'recurrence_type' and it's active, just create one
-                    created = fs_create_quest(user_id, t.__dict__)
-                    generated.append(created)
-                except Exception:
-                    continue
-            return generated
+            # Firestore mode: use robust template-generation helpers
+            from app.tasks.firestore_service import list_templates as fs_list_templates
+            from app.tasks.firestore_service import should_generate_template, generate_quest_from_template
+
+            templates = fs_list_templates(user_id)
+            generated = []
+            now = datetime.utcnow()
+            for t in templates:
+                try:
+                    # convert SimpleNamespace or dict to dict
+                    tdoc = t.__dict__ if hasattr(t, '__dict__') else dict(t)
+                    if should_generate_template(tdoc, now=now):
+                        created = generate_quest_from_template(tdoc, str(user_id))
+                        if created:
+                            generated.append(created)
+                except Exception:
+                    continue
+            return generated
     def trigger_generation(db: Session, template_id: int, user_id: int) -> Quest:
         if db is None:
-            tpl = fs_get_template(template_id)
-            if not tpl:
-                raise HTTPException(status_code=404, detail='Шаблон не найден')
-            return fs_create_quest(user_id, tpl.__dict__)
+            tpl = fs_get_template(template_id)
+            if not tpl:
+                raise HTTPException(status_code=404, detail='Шаблон не найден')
+            tdoc = tpl.__dict__ if hasattr(tpl, '__dict__') else dict(tpl)
+            from app.tasks.firestore_service import generate_quest_from_template
+            created = generate_quest_from_template(tdoc, str(user_id))
+            return created
         template = QuestTemplateService.get_template(db, template_id, user_id)
         if not template:
             raise HTTPException(status_code=404, detail="Шаблон не найден")
         return template.generate_quest(db)
