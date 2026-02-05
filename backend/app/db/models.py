from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
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
    is_public = Column(Boolean, default=False)

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

    # Plan chosen manually (A/B/C/LIFETIME)
    plan_slab = Column(String)

    # validity selected manually (days)
    validity_days_
