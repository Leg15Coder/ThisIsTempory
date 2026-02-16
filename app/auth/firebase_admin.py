import os
import json
from typing import Optional

try:
    import firebase_admin
    from firebase_admin import credentials, firestore, auth as firebase_auth
except Exception:
    firebase_admin = None
    credentials = None
    firestore = None
    firebase_auth = None


def init_firebase_admin(cred_json: Optional[str] = None):
    """Инициализация Firebase Admin SDK.

    Аргументы:
        cred_json: JSON-string с credentials. Если None - будет использовано окружение или файл.
    Возвращает экземпляр firestore.Client() или None.
    """
    if firebase_admin is None:
        raise RuntimeError('firebase_admin не установлен (pip install firebase_admin)')

    try:
        if firebase_admin._apps:
            return firestore.client()
    except Exception:
        pass

    cred = None

    if cred_json:
        try:
            cred_obj = json.loads(cred_json)
            cred = credentials.Certificate(cred_obj)
        except Exception as e:
            raise RuntimeError(f'Не удалось распарсить FIREBASE_CREDENTIALS: {e}')

    if cred is None:
        cred_path = os.environ.get('FIREBASE_CREDENTIALS_PATH')
        if cred_path and os.path.exists(cred_path):
            cred = credentials.Certificate(cred_path)

    if cred is None:
        env_json = os.environ.get('FIREBASE_CREDENTIALS')
        if env_json:
            try:
                cred_obj = json.loads(env_json)
                cred = credentials.Certificate(cred_obj)
            except Exception as e:
                raise RuntimeError(f'Не удалось распарсить FIREBASE_CREDENTIALS: {e}')

    if cred is None:
        default_path = os.path.join(os.getcwd(), 'firebase-credentials.json')
        if os.path.exists(default_path):
            cred = credentials.Certificate(default_path)

    if cred is None:
        return None

    firebase_admin.initialize_app(cred)
    return firestore.client()


_firestore_client = None


def get_firestore_client():
    global _firestore_client
    if _firestore_client is None:
        _firestore_client = init_firebase_admin(os.environ.get('FIREBASE_CREDENTIALS'))
    return _firestore_client
