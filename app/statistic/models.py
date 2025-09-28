from sqlalchemy import create_engine, Column, Integer, Float, String, DateTime, Date, ForeignKey


class BodyStats(Base):
    __tablename__ = "body_stats"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    date = Column(Date, default=datetime.now().date())
    age = Column(Integer)
    weight = Column(Integer)
    height = Column(Integer)
    body_fat = Column(Float)
    arm = Column(Integer)
    forearm = Column(Integer)
    wrist = Column(Integer)
    hip = Column(Integer)
    calf = Column(Integer)
    ass = Column(Integer)
    waist = Column(Integer)
    waist_with_thighs = Column(Integer)
    full_waist = Column(Integer)
    chest = Column(Integer)
    shoulders = Column(Integer)
    neck = Column(Integer)
