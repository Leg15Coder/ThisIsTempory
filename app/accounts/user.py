from sqlalchemy import Column, Integer, String, Boolean

from app.core.database import Base, get_db
from app.tasks.database import Quest


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    login = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)
    is_admin = Column(Boolean, default=False)

    def __repr__(self):
        return f"<User {self.login}>"


def get_user_by_login(login: str) -> User:
    with next(get_db()) as db:
        user = db.query(User).filter(User.login == login).all()
        if not user:
            return None
        return user[0]
