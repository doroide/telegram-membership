from sqlalchemy import (
    Column,
    Integer,
    BigInteger,
    String,
    Boolean,
    DateTime,
    Numeric,
    ForeignKey
)
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from backend.app.db.session import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)

    # ✅ FIX: Telegram IDs can exceed int32
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)

    username = Column(String(255))
    full_name = Column(String(255))

    current_tier = Column(Integer, default=3)
    is_lifetime_member = Column(Boolean, default=False)
    lifetime_amount = Column(Numeric(10, 2), default=0)

    channel_1_tier = Column(Integer)
    highest_amount_paid = Column(Numeric(10, 2), default=0)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    memberships = relationship("Membership", back_populates="user")
    payments = relationship("Payment", back_populates="user")
    upsell_attempts = relationship("UpsellAttempt", back_populates="user")


class Channel(Base):
    __tablename__ = "channels"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)

    telegram_chat_id = Column(String(255), unique=True, nullable=False)

    is_public = Column(Boolean, default=True)
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    memberships = relationship("Membership", back_populates="channel")
    payments = relationship("Payment", back_populates="channel")


class Membership(Base):
    __tablename__ = "memberships"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    channel_id = Column(Integer, ForeignKey("channels.id"), nullable=False)

    tier = Column(Integer, nullable=False)
    validity_days = Column(Integer, nullable=False)
    amount_paid = Column(Numeric(10, 2), nullable=False)

    start_date = Column(DateTime(timezone=True), nullable=False)
    expiry_date = Column(DateTime(timezone=True), nullable=False)

    is_active = Column(Boolean, default=True)

    auto_renew_enabled = Column(Boolean, default=False)
    razorpay_subscription_id = Column(String(255))
    subscription_status = Column(String(50))
    auto_renew_method = Column(String(50))

    reminded_7d = Column(Boolean, default=False)
    reminded_1d = Column(Boolean, default=False)
    reminded_expired = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="memberships")
    channel = relationship("Channel", back_populates="memberships")


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    channel_id = Column(Integer, ForeignKey("channels.id"), nullable=False)

    amount = Column(Numeric(10, 2), nullable=False)
    payment_id = Column(String(255), unique=True, nullable=False)
    status = Column(String(50), nullable=False)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="payments")
    channel = relationship("Channel", back_populates="payments")


class UpsellAttempt(Base):
    __tablename__ = "upsell_attempts"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    channel_id = Column(Integer, nullable=False)

    from_validity_days = Column(Integer, nullable=False)
    to_validity_days = Column(Integer, nullable=False)

    from_amount = Column(Numeric(10, 2), nullable=False)
    to_amount = Column(Numeric(10, 2), nullable=False)
    discount_amount = Column(Numeric(10, 2), nullable=False)

    accepted = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="upsell_attempts")

    is_manual = Column(Boolean, default=False)  # True if created by admin
    created_by_admin = Column(Integer, nullable=True)  # Admin user ID
    custom_message = Column(Text, nullable=True)  # Custom message from admin
