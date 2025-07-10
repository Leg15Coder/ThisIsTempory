from functools import wraps
from app.database import SessionLocal


def rarity_class(rarity: str) -> str:
    mapping = {
        "обычный": "common",
        "необычный": "uncommon",
        "редкий": "rare",
        "эпический": "epic",
        "легендарный": "legendary",
        "выполняется": "active",
        "проваленный": "failed",
        "завершённый": "finished"
    }
    return mapping.get(rarity.lower())


def Sessional(func):
    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        db = SessionLocal()
        try:
            kwargs["db"] = db
            result = await func(*args, **kwargs)
            db.commit()
            return result
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()

    return async_wrapper
