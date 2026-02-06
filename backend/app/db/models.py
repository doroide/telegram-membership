from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    BigInteger
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from backend.app.db.base import Base


# =========================================================
# USERS
# =========================================================
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)

    telegram_id = Column(BigInteger, unique=True, index=True, nullable=False)
    username = Column(String, nullable=True)
    full_name = Column(String, nullable=True)

    # Adult pricing slab decided by YOU (A / B / C / LIFETIME)
    plan_slab = Column(String, default="A")

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    memberships = relationship(
        "Membership",
        back_populates="user",
        cascade="all, delete-orphan"
    )


# =========================================================
# CHANNELS
# =========================================================
class Channel(Base):
    __tablename__ = "channels"

    id = Column(Integer, primary_key=True)

    name = Column(String, nullable=False)

    # Telegram private group/channel id
    telegram_chat_id = Column(BigInteger, nullable=False)

    # Visible to new users on /start
    is_public = Column(Boolean, default=True)

    # slab / fixed / custom (future safe)
    pricing_type = Column(String, default="slab")

    # disable anytime without deleting
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    memberships = relationship(
        "Membership",
        back_populates="channel",
        cascade="all, delete-orphan"
    )


# =========================================================
# MEMBERSHIPS (CORE BUSINESS TABLE)
# =========================================================
class Membership(Base):
    __tablename__ = "memberships"

    id = Column(Integer, primary_key=True)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    channel_id = Column(Integer, ForeignKey("channels.id"), nullable=False)

    plan_slab = Column(String)

    validity_days = Column(Integer)   # ✅ FIXED LINE

    amount_paid = Column(Integer)

    start_date = Column(DateTime(timezone=True), server_default=func.now())
    expiry_date = Column(DateTime(timezone=True))

    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="memberships")
    channel = relationship("Channel", back_populates="memberships")


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer)
    channel_id = Column(Integer)

    amount = Column(Float)
    payment_id = Column(String)
    status = Column(String)

    created_at = Column(DateTime, default=datetime.utcnow)
