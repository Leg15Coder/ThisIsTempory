from typing import Optional

from app.tasks.rarity_utils import normalize_to_quest_rarity


# Карта CSS-классов по имени enum
_RARITY_NAME_TO_CLASS = {
    'common': 'rarity-common',
    'uncommon': 'rarity-uncommon',
    'rare': 'rarity-rare',
    'epic': 'rarity-epic',
    'legendary': 'rarity-legendary',
}


def rarity_class(rarity: Optional[object]) -> Optional[str]:
    """
    Возвращает CSS-класс для редкости. Принимает строку (ключ или метку) или enum.
    """
    if not rarity:
        return None
    try:
        qr = normalize_to_quest_rarity(rarity)
    except Exception:
        return None
    return _RARITY_NAME_TO_CLASS.get(qr.name, 'rarity-common')
