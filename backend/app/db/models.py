from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Boolean,
    Numeric,
)
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    __table_args__ = {"schema": "public"}  # 🔴 THIS IS THE FIX

    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False)

    plan_id = Column(String, nullable=True)

    status = Column(String, default="inactive")
    expiry_date = Column(DateTime, nullable=True)

    reminded_3d = Column(Boolean, default=False)
    reminded_1d = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = {"schema": "public"}  # 🔴 THIS IS THE FIX

    id = Column(Integer, primary_key=True)

    telegram_id = Column(Integer, nullable=False)
    plan_id = Column(String, nullable=False)

    razorpay_payment_id = Column(String, unique=True, nullable=False)
    amount = Column(Numeric, nullable=False)

    paid_at = Column(DateTime, default=datetime.utcnow)
