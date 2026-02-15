import os
from dotenv import load_dotenv
load_dotenv()
import firebase_admin
from firebase_admin import credentials, auth
from fastapi import HTTPException, status
from typing import Dict, Any


class FirebaseAuthService:
    def __init__(self):
        self.initialized = False
        self._initialize()

    def _initialize(self):
        if firebase_admin._apps:
            self.initialized = True
            return
        cred_path = os.getenv('FIREBASE_CREDENTIALS_PATH')
        if not cred_path or not os.path.exists(cred_path):
            self.initialized = False
            print('⚠️ Файл с учетными данными Firebase не найден; функции Firebase отключены')
            return
        try:
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred)
            self.initialized = True
            print('✅ Firebase Admin инициализирован')
        except Exception as e:
            self.initialized = False
            print('⚠️ Ошибка инициализации Firebase:', str(e))

    def verify_id_token(self, id_token: str) -> Dict[str, Any]:
        if not self.initialized:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail='Firebase не настроен')
        try:
            decoded = auth.verify_id_token(id_token)
            return decoded
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f'Неверный Firebase токен: {str(e)}')


firebase_service = FirebaseAuthService()
