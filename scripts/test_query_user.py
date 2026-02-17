from app.tasks.database import SessionLocal
from app.auth.models import User

s = SessionLocal()
try:
    u = s.query(User).filter(User.id == 1).first()
    print('User:', u)
    if u:
        print('email=', u.email, 'currency=', getattr(u,'currency', None))
except Exception as e:
    print('EXCEPTION:', e)
finally:
    s.close()
