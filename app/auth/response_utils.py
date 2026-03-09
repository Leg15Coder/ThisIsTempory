from datetime import datetime
from types import SimpleNamespace
from typing import Any

from app.auth.schemas import UserResponse


def _to_mapping(user: Any) -> dict:
    if isinstance(user, dict):
        return dict(user)
    if isinstance(user, SimpleNamespace):
        return vars(user).copy()
    data = {}
    for field in (
        'id', 'email', 'username', 'display_name', 'avatar_url', 'bio',
        'is_verified', 'created_at'
    ):
        if hasattr(user, field):
            data[field] = getattr(user, field)
    return data


def to_user_response(user: Any) -> UserResponse:
    data = _to_mapping(user)

    data.setdefault('username', None)
    data.setdefault('avatar_url', None)
    data.setdefault('bio', None)
    data.setdefault('is_verified', False)
    data.setdefault('display_name', data.get('email', '').split('@')[0] if data.get('email') else '')

    created_at = data.get('created_at')
    if not created_at:
        data['created_at'] = datetime.now()
    elif isinstance(created_at, str):
        try:
            data['created_at'] = datetime.fromisoformat(created_at)
        except Exception:
            data['created_at'] = datetime.now()

    return UserResponse.model_validate(data)
