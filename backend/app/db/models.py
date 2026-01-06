from sqlalchemy import (
    Column,
    BigInteger,
    String,
    Boolean,
    DateTime,
    Integer,
)
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False)

    telegram_username = Column(String)
    plan_id = Column(String)
    razorpay_payment_id = Column(String)

    status = Column(String, default="active")

    start_date = Column(DateTime)
    expiry_date = Column(DateTime)
    next_renewal = Column(DateTime)

    payment_method = Column(String)
    attempts_failed = Column(Integer, default=0)

    reminded_3d = Column(Boolean, default=False)
    reminded_1d = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_user_id = Column(BigInteger, nullable=False)

    plan_id = Column(String, nullable=False)
    expires_at = Column(DateTime, nullable=False)

    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
