"""
Минимальная реализация операций с Firestore для квестов, шаблонов и магазина.
Это облегчённый адаптер: хранит подзадачи внутри документа квеста.
"""
from datetime import datetime
from types import SimpleNamespace
from typing import List, Optional, Dict, Any
from app.auth.firebase_admin import get_firestore_client


def _doc_to_quest_obj(doc) -> SimpleNamespace:
    data = doc.to_dict()
    data['id'] = doc.id
    # Convert datetime strings to datetime if needed
    if 'deadline' in data and isinstance(data['deadline'], str):
        try:
            data['deadline'] = datetime.fromisoformat(data['deadline'])
        except Exception:
            pass
    # ensure subtasks list
    data.setdefault('subtasks', [])
    return SimpleNamespace(**data)


def list_quests(user_id: str, status: Optional[str] = None) -> List[SimpleNamespace]:
    client = get_firestore_client()
    if not client:
        return []
    col = client.collection('quests')
    q = col.where('user_id', '==', str(user_id))
    if status is not None:
        q = q.where('status', '==', status)
    docs = list(q.stream())
    return [_doc_to_quest_obj(d) for d in docs]


def get_quest(quest_id: str) -> Optional[SimpleNamespace]:
    client = get_firestore_client()
    if not client:
        return None
    doc = client.collection('quests').document(str(quest_id)).get()
    if not doc.exists:
        return None
    return _doc_to_quest_obj(doc)


def create_quest(user_id: str, payload: Dict[str, Any]) -> SimpleNamespace:
    client = get_firestore_client()
    if not client:
        raise RuntimeError('Firestore not initialized')
    col = client.collection('quests')
    data = payload.copy()
    data['user_id'] = str(user_id)
    data.setdefault('created', datetime.utcnow().isoformat())
    # store deadline as ISO
    if 'deadline' in data and isinstance(data['deadline'], datetime):
        data['deadline'] = data['deadline'].isoformat()
    # ensure subtasks
    data.setdefault('subtasks', [])
    # parents as list
    data.setdefault('parents', [])
    data.setdefault('status', 'active')

    doc_ref = col.document()
    doc_ref.set(data)
    doc = doc_ref.get()
    return _doc_to_quest_obj(doc)


def update_quest(quest_id: str, fields: Dict[str, Any]) -> Optional[SimpleNamespace]:
    client = get_firestore_client()
    if not client:
        return None
    doc_ref = client.collection('quests').document(str(quest_id))
    doc_ref.update(fields)
    doc = doc_ref.get()
    return _doc_to_quest_obj(doc)


def delete_quest(quest_id: str) -> bool:
    client = get_firestore_client()
    if not client:
        return False
    client.collection('quests').document(str(quest_id)).delete()
    return True


# Shop items

def list_shop_items(user_id: str, available_only: bool = True) -> List[SimpleNamespace]:
    client = get_firestore_client()
    if not client:
        return []
    col = client.collection('shop_items')
    q = col.where('user_id', '==', str(user_id))
    if available_only:
        q = q.where('is_available', '==', True)
    docs = list(q.stream())
    return [SimpleNamespace(**{**d.to_dict(), 'id': d.id}) for d in docs]


def create_shop_item(user_id: str, data: Dict[str, Any]) -> SimpleNamespace:
    client = get_firestore_client()
    if not client:
        raise RuntimeError('Firestore not initialized')
    col = client.collection('shop_items')
    payload = data.copy()
    payload['user_id'] = str(user_id)
    payload.setdefault('created_at', datetime.utcnow().isoformat())
    doc_ref = col.document()
    doc_ref.set(payload)
    doc = doc_ref.get()
    return SimpleNamespace(**{**doc.to_dict(), 'id': doc.id})


def get_shop_item(user_id: str, item_id: str) -> Optional[SimpleNamespace]:
    client = get_firestore_client()
    if not client:
        return None
    doc = client.collection('shop_items').document(str(item_id)).get()
    if not doc.exists:
        return None
    d = doc.to_dict()
    if str(d.get('user_id')) != str(user_id):
        return None
    return SimpleNamespace(**{**d, 'id': doc.id})


def update_shop_item(item_id: str, fields: Dict[str, Any]) -> Optional[SimpleNamespace]:
    client = get_firestore_client()
    if not client:
        return None
    doc_ref = client.collection('shop_items').document(str(item_id))
    doc_ref.update(fields)
    doc = doc_ref.get()
    return SimpleNamespace(**{**doc.to_dict(), 'id': doc.id})


# Inventory

def list_inventory(user_id: str) -> List[SimpleNamespace]:
    client = get_firestore_client()
    if not client:
        return []
    col = client.collection('inventory')
    q = col.where('user_id', '==', str(user_id))
    docs = list(q.stream())
    return [SimpleNamespace(**{**d.to_dict(), 'id': d.id}) for d in docs]


def create_inventory_entry(user_id: str, item_id: str, quantity: int = 1) -> SimpleNamespace:
    client = get_firestore_client()
    if not client:
        raise RuntimeError('Firestore not initialized')
    col = client.collection('inventory')
    payload = {
        'user_id': str(user_id),
        'shop_item_id': str(item_id),
        'quantity': quantity,
        'used_quantity': 0,
        'purchased_at': datetime.utcnow().isoformat()
    }
    doc_ref = col.document()
    doc_ref.set(payload)
    doc = doc_ref.get()
    return SimpleNamespace(**{**doc.to_dict(), 'id': doc.id})


def update_inventory_entry(entry_id: str, fields: Dict[str, Any]) -> Optional[SimpleNamespace]:
    client = get_firestore_client()
    if not client:
        return None
    doc_ref = client.collection('inventory').document(str(entry_id))
    doc_ref.update(fields)
    doc = doc_ref.get()
    return SimpleNamespace(**{**doc.to_dict(), 'id': doc.id})


# --- Пользователь и операции с валютой (atomic) ---
def get_user(user_id: str) -> Optional[SimpleNamespace]:
    client = get_firestore_client()
    if not client:
        return None
    doc = client.collection('users').document(str(user_id)).get()
    if not doc.exists:
        return None
    return SimpleNamespace(**{**doc.to_dict(), 'id': doc.id})


def update_user_currency(user_id: str, delta: int) -> Optional[SimpleNamespace]:
    """Atomically change user.currency by delta (может быть отрицательным). Возвращает обновлённый user or None."""
    client = get_firestore_client()
    if not client:
        raise RuntimeError('Firestore not initialized')

    user_ref = client.collection('users').document(str(user_id))

    def txn_update(txn):
        snap = user_ref.get(transaction=txn)
        if not snap.exists:
            raise RuntimeError('User not found')
        data = snap.to_dict()
        curr = int(data.get('currency', 0))
        new = curr + int(delta)
        if new < 0:
            raise RuntimeError('Not enough currency')
        txn.update(user_ref, {'currency': new, 'updated_at': datetime.utcnow().isoformat()})

    try:
        client.transaction()(txn_update)
    except Exception as e:
        raise

    doc = user_ref.get()
    return SimpleNamespace(**{**doc.to_dict(), 'id': doc.id})


# --- Транзакция покупки предмета ---
def purchase_shop_item(user_id: str, shop_item_id: str, quantity: int = 1) -> SimpleNamespace:
    client = get_firestore_client()
    if not client:
        raise RuntimeError('Firestore not initialized')

    user_ref = client.collection('users').document(str(user_id))
    item_ref = client.collection('shop_items').document(str(shop_item_id))
    inventory_col = client.collection('inventory')

    def txn_purchase(txn):
        user_snap = user_ref.get(transaction=txn)
        item_snap = item_ref.get(transaction=txn)
        if not user_snap.exists:
            raise RuntimeError('User not found')
        if not item_snap.exists:
            raise RuntimeError('Item not found')

        user_data = user_snap.to_dict()
        item_data = item_snap.to_dict()

        price = int(item_data.get('price', 0))
        stock = item_data.get('stock', None)
        available = item_data.get('is_available', True)

        if not available:
            raise RuntimeError('Item not available')

        total_cost = price * int(quantity)
        curr = int(user_data.get('currency', 0))
        if curr < total_cost:
            raise RuntimeError('Not enough currency')

        if stock is not None:
            stock = int(stock)
            if stock < quantity:
                raise RuntimeError('Not enough stock')
            txn.update(item_ref, {'stock': stock - quantity})

        txn.update(user_ref, {'currency': curr - total_cost, 'updated_at': datetime.utcnow().isoformat()})

        # create inventory entry
        inv_doc = inventory_col.document()
        inv_doc.set({
            'user_id': str(user_id),
            'shop_item_id': str(shop_item_id),
            'quantity': int(quantity),
            'used_quantity': 0,
            'purchased_at': datetime.utcnow().isoformat()
        }, transaction=txn)

    txn = client.transaction()
    try:
        txn(txn_purchase)
    except Exception as e:
        raise

    # return newly created inventory item(s) and updated user
    user_doc = user_ref.get()
    return SimpleNamespace(**{**user_doc.to_dict(), 'id': user_doc.id})


# --- Шаблоны квестов ---
def list_templates(user_id: str) -> List[SimpleNamespace]:
    client = get_firestore_client()
    if not client:
        return []
    col = client.collection('quest_templates')
    q = col.where('user_id', '==', str(user_id))
    docs = list(q.stream())
    return [SimpleNamespace(**{**d.to_dict(), 'id': d.id}) for d in docs]


def create_template(user_id: str, data: Dict[str, Any]) -> SimpleNamespace:
    client = get_firestore_client()
    if not client:
        raise RuntimeError('Firestore not initialized')
    col = client.collection('quest_templates')
    payload = data.copy()
    payload['user_id'] = str(user_id)
    payload.setdefault('created_at', datetime.utcnow().isoformat())
    doc_ref = col.document()
    doc_ref.set(payload)
    doc = doc_ref.get()
    return SimpleNamespace(**{**doc.to_dict(), 'id': doc.id})


def get_template(template_id: str) -> Optional[SimpleNamespace]:
    client = get_firestore_client()
    if not client:
        return None
    doc = client.collection('quest_templates').document(str(template_id)).get()
    if not doc.exists:
        return None
    d = doc.to_dict()
    return SimpleNamespace(**{**d, 'id': doc.id})


def update_template(template_id: str, fields: Dict[str, Any]) -> Optional[SimpleNamespace]:
    client = get_firestore_client()
    if not client:
        return None
    doc_ref = client.collection('quest_templates').document(str(template_id))
    doc_ref.update(fields)
    doc = doc_ref.get()
    return SimpleNamespace(**{**doc.to_dict(), 'id': doc.id})


def delete_template(template_id: str) -> bool:
    client = get_firestore_client()
    if not client:
        return False
    client.collection('quest_templates').document(str(template_id)).delete()
    return True


# --- Helpers for templates generation ---
def _parse_iso(dt_str: Optional[str]):
    if not dt_str:
        return None
    try:
        return datetime.fromisoformat(dt_str)
    except Exception:
        return None


def should_generate_template(tpl_doc: Dict[str, Any], now: Optional[datetime] = None) -> bool:
    """Проверяет, нужно ли сгенерировать квест по шаблону (данные документа как dict)."""
    if now is None:
        now = datetime.utcnow()

    if not tpl_doc.get('is_active', True):
        return False

    start_at = _parse_iso(tpl_doc.get('start_at'))
    end_at = _parse_iso(tpl_doc.get('end_at'))
    last_generated = _parse_iso(tpl_doc.get('last_generated'))

    if start_at and now < start_at:
        return False
    if end_at and now > end_at:
        return False

    rtype = tpl_doc.get('recurrence_type')
    if rtype == 'daily':
        # if never generated -> generate; if last_generated is before today -> generate
        if last_generated is None:
            return True
        return last_generated.date() < now.date()

    if rtype == 'weekly':
        weekdays = tpl_doc.get('weekdays')
        if not weekdays:
            return False
        try:
            target = [int(x) for x in str(weekdays).split(',') if x != '']
        except Exception:
            return False
        wd = now.weekday()  # 0=Monday
        if wd not in target:
            return False
        if last_generated is None:
            return True
        return last_generated.date() < now.date()

    if rtype == 'interval':
        interval = tpl_doc.get('interval_hours')
        if not interval:
            return False
        try:
            interval = float(interval)
        except Exception:
            return False
        if last_generated is None:
            return True
        elapsed = (now - last_generated).total_seconds() / 3600.0
        return elapsed >= interval

    return False


def generate_quest_from_template(template_doc: Dict[str, Any], user_id: str) -> Optional[SimpleNamespace]:
    """Создает квест в коллекции quests на основе шаблона doc (dict) и помечает last_generated."""
    client = get_firestore_client()
    if not client:
        return None

    tpl = template_doc.copy()
    payload = {
        'title': tpl.get('title'),
        'author': tpl.get('author', '???'),
        'description': tpl.get('description', ''),
        'cost': int(tpl.get('cost', 0)),
        'rarity': tpl.get('rarity', 'Обычный'),
        'scope': tpl.get('scope'),
        'parents': tpl.get('parents', []),
        'subtasks': tpl.get('subtasks', []),
        'status': 'active'
    }

    # duration_hours -> deadline
    try:
        duration = int(tpl.get('duration_hours', 24))
    except Exception:
        duration = 24
    deadline = datetime.utcnow() + __import__('datetime').timedelta(hours=duration)
    payload['deadline'] = deadline.isoformat()

    created = create_quest(user_id, payload)

    # update last_generated on template doc
    try:
        t_ref = client.collection('quest_templates').document(str(tpl.get('id')))
        t_ref.update({'last_generated': datetime.utcnow().isoformat()})
    except Exception:
        pass

    return created
