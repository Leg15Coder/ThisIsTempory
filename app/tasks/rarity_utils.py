from typing import Any

from app.tasks.database import QuestRarity, ItemRarity


def _normalize_enum_by_name_or_value(enum_cls, v, default):
    # If already enum
    if isinstance(v, enum_cls):
        return v
    if v is None:
        return default
    # Strings: try name, then value, then lower-name, then lower-value
    if isinstance(v, str):
        # direct by name
        try:
            return enum_cls[v]
        except Exception:
            pass
        # direct by value
        try:
            return enum_cls(v)
        except Exception:
            pass
        rv = v.lower()
        # try name lower
        for m in enum_cls:
            if m.name.lower() == rv:
                return m
        # try value lower
        for m in enum_cls:
            if str(m.value).lower() == rv:
                return m
    # fallback
    return default


def normalize_to_quest_rarity(v: Any) -> QuestRarity:
    """Нормализует вход (name, value, enum) в QuestRarity. Возвращает QuestRarity.common по умолчанию."""
    return _normalize_enum_by_name_or_value(QuestRarity, v, QuestRarity.common)


def normalize_to_item_rarity(v: Any) -> ItemRarity:
    """Нормализует вход в ItemRarity (для магазина). Возвращает ItemRarity.common по умолчанию."""
    return _normalize_enum_by_name_or_value(ItemRarity, v, ItemRarity.common)


def display_label_from_quest_rarity(v: Any) -> str:
    """Возвращает строковое значение (метку) для QuestRarity.
    Принимает и строку, и enum.
    """
    qr = normalize_to_quest_rarity(v)
    return qr.value


def display_label_from_item_rarity(v: Any) -> str:
    ir = normalize_to_item_rarity(v)
    return ir.value


def key_from_quest_rarity(v: Any) -> str:
    """Возвращает имя (ключ) редкости, например 'common', 'rare' — удобно для value в <select> на фронтенде."""
    qr = normalize_to_quest_rarity(v)
    return qr.name


def key_from_item_rarity(v: Any) -> str:
    ir = normalize_to_item_rarity(v)
    return ir.name

