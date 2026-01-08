from sqlalchemy import (
    Column,
    BigInteger,
    String,
    Boolean,
    DateTime,
    Integer,
    ForeignKey,
)
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime

Base = declarative_base()


# ================================
# USER MODEL
# ================================
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

    # Relationship to payments
    payments = relationship("Payment", back_populates="user", cascade="all, delete-orphan")


# ================================
# PAYMENT MODEL (MISSING EARLIER)
# ================================
class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, autoincrement=True)

    payment_id = Column(String, unique=True)
    amount = Column(Integer)
    currency = Column(String, default="INR")

    user_id = Column(BigInteger, ForeignKey("users.telegram_id"))
    plan_id = Column(String)
    status = Column(String)  # created, paid, failed

    created_at = Column(DateTime, default=datetime.utcnow)

    # Back reference to User
    user = relationship("User", back_populates="payments")


# ================================
# SUBSCRIPTION MODEL (OPTIONAL)
# Still included if you want logs
# ================================
class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_user_id = Column(BigInteger, nullable=False)

    plan_id = Column(String, nullable=False)
    expires_at = Column(DateTime, nullable=False)

    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
