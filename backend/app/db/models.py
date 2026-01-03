from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

# ----------------------------
# PLANS TABLE
# ----------------------------
class Plan(Base):
    __tablename__ = "plans"

    id = Column(Integer, primary_key=True, index=True)
    plan_key = Column(String, unique=True)             # e.g., "basic_99"
    razorpay_plan_id = Column(String)                  # Razorpay plan id
    price = Column(Integer)                            # 99, 199 etc.
    billing_cycle = Column(String, default="monthly")  # billing frequency
    description = Column(String)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    users = relationship("User", back_populates="plan")


# ----------------------------
# USERS TABLE
# ----------------------------
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, index=True)  # Telegram user ID
    telegram_username = Column(String)
    plan_id = Column(Integer, ForeignKey("plans.id"))
    razorpay_subscription_id = Column(String)
    status = Column(String)                     # active / expired / cancelled
    start_date = Column(DateTime)
    expiry_date = Column(DateTime)
    next_renewal = Column(DateTime)
    payment_method = Column(String)
    attempts_failed = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    plan = relationship("Plan", back_populates="users")
    payments = relationship("Payment", back_populates="user")


# ----------------------------
# PAYMENTS TABLE
# ----------------------------
class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    razorpay_payment_id = Column(String)
    amount = Column(Integer)        # amount in paise
    status = Column(String)         # success / failed
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="payments")

class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True)
    telegram_user_id = Column(String, index=True, nullable=False)
    plan_id = Column(String, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    active = Column(Boolean, default=True)