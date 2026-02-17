from typing import Optional


RARITY_STATUS_MAPPING = {
    "обычный": "common",
    "необычный": "uncommon",
    "редкий": "rare",
    "эпический": "epic",
    "легендарный": "legendary",
    "выполняется": "active",
    "проваленный": "failed",
    "завершённый": "finished",
    "неактивный": "inactive",
    "абстрактный": "abstract"
}


def rarity_class(rarity: str) -> Optional[str]:
    """
    Преобразует название редкости/статуса квеста в CSS-класс.

    Args:
        rarity: Название редкости или статуса квеста

    Returns:
        CSS-класс или None если значение не найдено
    """
    if not rarity:
        return None
    return RARITY_STATUS_MAPPING.get(rarity.lower())
