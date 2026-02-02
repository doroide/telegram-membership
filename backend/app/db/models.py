from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Boolean,
    DateTime,
    ForeignKey,
    BigInteger,
    Numeric
)

from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from backend.app.db.base import Base


# =========================================================
# USER
# =========================================================

class User(Base):
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True)

    username = Column(String(255), nullable=True)
    full_name = Column(String(255), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    total_spent = Column(Numeric, default=0)
    tier = Column(String(20), default="Budget")

    memberships = relationship("Membership", back_populates="user")
    payments = relationship("Payment", back_populates="user")
    access_requests = relationship("AccessRequest", back_populates="user")


# =========================================================
# PAYMENT
# =========================================================

class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True)

    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"))

    amount = Column(Numeric, nullable=False)
    currency = Column(String(10), default="INR")

    razorpay_payment_id = Column(String(255), nullable=True)
    status = Column(String(50), default="created")

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    membership_id = Column(Integer, ForeignKey("memberships.id"), nullable=True)

    user = relationship("User", back_populates="payments")
    membership = relationship("Membership", back_populates="payments")


# =========================================================
# CHANNEL
# =========================================================

class Channel(Base):
    __tablename__ = "channels"

    id = Column(Integer, primary_key=True)

    name = Column(String(255), nullable=False)
    telegram_chat_id = Column(BigInteger, unique=True, nullable=False)

    description = Column(Text, nullable=True)

    invite_link = Column(Text, nullable=True)

    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    memberships = relationship("Membership", back_populates="channel")
    requests = relationship("AccessRequest", back_populates="channel")


# =========================================================
# ACCESS REQUEST
# =========================================================

class AccessRequest(Base):
    __tablename__ = "access_requests"

    id = Column(Integer, primary_key=True)

    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"))
    channel_id = Column(Integer, ForeignKey("channels.id"))

    status = Column(String(20), default="pending")

    admin_id = Column(BigInteger, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    processed_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="access_requests")
    channel = relationship("Channel", back_populates="requests")


# =========================================================
# MEMBERSHIP
# =========================================================

class Membership(Base):
    __tablename__ = "memberships"

    id = Column(Integer, primary_key=True)

    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"))
    channel_id = Column(Integer, ForeignKey("channels.id"))

    plan = Column(String(20), nullable=False)

    start_date = Column(DateTime(timezone=True), server_default=func.now())
    expiry_date = Column(DateTime(timezone=True), nullable=True)

    is_active = Column(Boolean, default=True)

    reminders_sent = Column(Text, default="{}")

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="memberships")
    channel = relationship("Channel", back_populates="memberships")
    payments = relationship("Payment", back_populates="membership")
