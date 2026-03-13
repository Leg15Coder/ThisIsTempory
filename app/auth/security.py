import os
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from jose import jwt, JWTError
import base64
import secrets as _secrets
import hmac
import hashlib
from fastapi import HTTPException, status

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-me-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", 30))


def _truncate_password_for_bcrypt(password: str) -> str:
    """Обрезать пароль до 72 байт для совместимости с bcrypt.

    bcrypt игнорирует байты после 72, и passlib вызывает ValueError, если
    предоставлены более длинные байты при вычислении устаревших проверок, поэтому
    мы нормализуем, обрезая до допустимой UTF-8 строки длиной до 72 байт.
    """
    if not isinstance(password, str):
        password = str(password or "")
    b = password.encode('utf-8')
    if len(b) <= 72:
        return password
    truncated = b[:72]
    # декодировать, игнорируя поврежденный хвост, чтобы избежать UnicodeDecodeError
    return truncated.decode('utf-8', errors='ignore')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password using pbkdf2_sha256 format: algorithm$iterations$salt_b64$hash_b64"""
    try:
        truncated = _truncate_password_for_bcrypt(plain_password)
        parts = hashed_password.split('$')
        if len(parts) != 4:
            return False
        algorithm, iterations_s, salt_b64, hash_b64 = parts
        if algorithm != 'pbkdf2_sha256':
            return False
        iterations = int(iterations_s)
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(hash_b64)
        dk = hashlib.pbkdf2_hmac('sha256', truncated.encode('utf-8'), salt, iterations)
        return hmac.compare_digest(dk, expected)
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    """Get password hash in format pbkdf2_sha256$iterations$salt_b64$hash_b64"""
    truncated = _truncate_password_for_bcrypt(password)
    iterations = 260000
    salt = _secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac('sha256', truncated.encode('utf-8'), salt, iterations)
    return f"pbkdf2_sha256${iterations}${base64.b64encode(salt).decode('ascii')}${base64.b64encode(dk).decode('ascii')}"


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "type": "access"})
    token = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return token


def create_refresh_token(data: Dict[str, Any]) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    token = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return token


def decode_token(token: str) -> Dict[str, Any]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Не удалось проверить токен",
            headers={"WWW-Authenticate": "Bearer"}
        )


def validate_password(password: str) -> bool:
    return isinstance(password, str) and len(password) >= 8


def prepare_password(password: str) -> str:
    """Public helper: return a password truncated to bcrypt-compatible length (72 bytes).

    Use this before calling hashing functions from other modules when in doubt about
    underlying hashing backend.
    """
    return _truncate_password_for_bcrypt(password)
