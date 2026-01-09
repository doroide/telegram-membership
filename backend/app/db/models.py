from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime
from sqlalchemy.sql import func
from backend.app.db.base import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Store Telegram ID as TEXT
    telegram_id = Column(Text, unique=True, nullable=False)

    telegram_username = Column(Text, nullable=True)

    plan_id = Column(Text, nullable=True)
    razorpay_payment_id = Column(Text, nullable=True)
    status = Column(Text, default="active")

    start_date = Column(DateTime, nullable=True)
    expiry_date = Column(DateTime, nullable=True)
    next_renewal = Column(DateTime, nullable=True)
    payment_method = Column(Text, nullable=True)

    attempts_failed = Column(Integer, default=0)
    reminded_3d = Column(Boolean, default=False)
    reminded_1d = Column(Boolean, default=False)

    created_at = Column(DateTime, default=func.now())
