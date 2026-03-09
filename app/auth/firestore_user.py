"""
Небольшой адаптер для работы с пользователями в Firestore.
Используется в режиме FIRESTORE_ENABLED, когда SQLAlchemy не доступен.
"""
from typing import Optional, Dict, Any
from types import SimpleNamespace

from app.auth.firebase_admin import get_firestore_client


def _doc_to_user_obj(doc) -> SimpleNamespace:
    data = doc.to_dict()
    data['id'] = doc.id
    return SimpleNamespace(**data)


def get_user_by_email(email: str) -> Optional[SimpleNamespace]:
    client = get_firestore_client()
    if not client:
        return None
    users = client.collection('users')
    q = users.where('email', '==', email).limit(1).stream()
    docs = list(q)
    if docs:
        return _doc_to_user_obj(docs[0])
    return None


def get_user_by_id(user_id: str) -> Optional[SimpleNamespace]:
    client = get_firestore_client()
    if not client:
        return None
    doc = client.collection('users').document(str(user_id)).get()
    if doc.exists:
        return _doc_to_user_obj(doc)
    return None


def get_user_by_firebase_uid(firebase_uid: str) -> Optional[SimpleNamespace]:
    client = get_firestore_client()
    if not client:
        return None
    users = client.collection('users')
    q = users.where('firebase_uid', '==', firebase_uid).limit(1).stream()
    docs = list(q)
    if docs:
        return _doc_to_user_obj(docs[0])
    return None


def create_user(data: Dict[str, Any]) -> SimpleNamespace:
    client = get_firestore_client()
    if not client:
        raise RuntimeError('Firestore not initialized')
    users = client.collection('users')
    # if id provided, set doc id
    doc_id = data.get('id')
    if doc_id:
        doc_ref = users.document(str(doc_id))
        # ensure defaults
        data_to_save = data.copy()
        data_to_save.setdefault('currency', 0)
        data_to_save.setdefault('is_verified', False)
        data_to_save.setdefault('created_at', __import__('datetime').datetime.utcnow().isoformat())
        # remove explicit None values
        for k in list(data_to_save.keys()):
            if data_to_save[k] is None:
                data_to_save.pop(k)
        doc_ref.set(data_to_save)
        doc = doc_ref.get()
        return _doc_to_user_obj(doc)
    else:
        doc_ref = users.document()
        data_to_save = data.copy()
        # set defaults
        data_to_save.setdefault('currency', 0)
        data_to_save.setdefault('is_verified', False)
        data_to_save.setdefault('created_at', __import__('datetime').datetime.utcnow().isoformat())
        # do not store None values
        for k in list(data_to_save.keys()):
            if data_to_save[k] is None:
                data_to_save.pop(k)
        doc_ref.set(data_to_save)
        doc = doc_ref.get()
        return _doc_to_user_obj(doc)


def update_user(doc_id: str, fields: Dict[str, Any]) -> Optional[SimpleNamespace]:
    client = get_firestore_client()
    if not client:
        return None
    doc_ref = client.collection('users').document(str(doc_id))
    doc_ref.update(fields)
    doc = doc_ref.get()
    return _doc_to_user_obj(doc)


def delete_user(doc_id: str):
    client = get_firestore_client()
    if not client:
        return False
    client.collection('users').document(str(doc_id)).delete()
    return True
