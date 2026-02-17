import os
from dotenv import load_dotenv
load_dotenv()

try:
    import firebase_admin
    from firebase_admin import credentials, auth
except Exception:
    firebase_admin = None
    credentials = None
    auth = None

from fastapi import HTTPException, status
from typing import Dict, Any

try:
    from app.auth.firebase_admin import init_firebase_admin
except Exception:
    init_firebase_admin = None


class FirebaseAuthService:
    def __init__(self):
        self.initialized = False
        self._initialize()

    def _initialize(self):
        try:
            if firebase_admin and getattr(firebase_admin, '_apps', None):
                self.initialized = True
                return
        except Exception:
            pass

        if init_firebase_admin:
            try:
                client = init_firebase_admin(os.environ.get('FIREBASE_CREDENTIALS'))
                if client is not None or (firebase_admin and getattr(firebase_admin, '_apps', None)):
                    self.initialized = True
                    print('✅ Firebase Admin инициализирован (через init_firebase_admin)')
                    return
            except Exception as e:
                print('⚠️ Ошибка init_firebase_admin:', e)

        cred_path = os.getenv('FIREBASE_CREDENTIALS_PATH')
        if cred_path and os.path.exists(cred_path):
            try:
                cred = credentials.Certificate(cred_path)
                firebase_admin.initialize_app(cred)
                self.initialized = True
                print('✅ Firebase Admin инициализирован (по пути)')
                return
            except Exception as e:
                print('⚠️ Ошибка инициализации Firebase по пути:', str(e))

        env_json = os.environ.get('FIREBASE_CREDENTIALS')
        if env_json:
            try:
                import json
                cred_obj = json.loads(env_json)
                cred = credentials.Certificate(cred_obj)
                firebase_admin.initialize_app(cred)
                self.initialized = True
                print('✅ Firebase Admin инициализирован (из FIREBASE_CREDENTIALS)')
                return
            except Exception as e:
                print('⚠️ Не удалось распарсить FIREBASE_CREDENTIALS:', e)

        default_path = os.path.join(os.getcwd(), 'firebase-credentials.json')
        if os.path.exists(default_path):
            try:
                cred = credentials.Certificate(default_path)
                firebase_admin.initialize_app(cred)
                self.initialized = True
                print('✅ Firebase Admin инициализирован (локальный файл)')
                return
            except Exception as e:
                print('⚠️ Ошибка инициализации Firebase (локальный файл):', str(e))

        self.initialized = False
        print('⚠️ Файл с учетными данными Firebase не найден; функции Firebase отключены')

    def verify_id_token(self, id_token: str) -> Dict[str, Any]:
        if not self.initialized:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail='Firebase не настроен')
        try:
            decoded = auth.verify_id_token(id_token)
            return decoded
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f'Неверный Firebase токен: {str(e)}')


firebase_service = FirebaseAuthService()
