from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    BigInteger,
    JSON
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
    
    # Tier tracking
    current_tier = Column(Integer, default=3)  # New users start at Tier 3
    channel_1_tier = Column(Integer, nullable=True)  # Locked tier for Channel 1
    highest_amount_paid = Column(Integer, default=0)  # Track highest payment
    
    # Lifetime tracking
    is_lifetime_member = Column(Boolean, default=False)
    lifetime_amount = Column(Integer, nullable=True)  # Last lifetime amount paid
    
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
    telegram_chat_id = Column(BigInteger, nullable=False)
    
    # Visibility control
    is_public = Column(Boolean, default=True)  # True for channels 1-4, False for 5-10
    
    # Channel management
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    memberships = relationship(
        "Membership",
        back_populates="channel",
        cascade="all, delete-orphan"
    )

# =========================================================
# MEMBERSHIPS
# =========================================================
class Membership(Base):
    __tablename__ = "memberships"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    channel_id = Column(Integer, ForeignKey("channels.id"), nullable=False)
    
    # Pricing details
    tier = Column(Integer)  # Which tier was used for this purchase
    validity_days = Column(Integer)
    amount_paid = Column(Integer)
    
    # Dates
    start_date = Column(DateTime(timezone=True), server_default=func.now())
    expiry_date = Column(DateTime(timezone=True))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    user = relationship("User", back_populates="memberships")
    channel = relationship("Channel", back_populates="memberships")

# =========================================================
# PAYMENTS
# =========================================================
class Payment(Base):
    __tablename__ = "payments"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer)
    channel_id = Column(Integer)
    amount = Column(Float)
    payment_id = Column(String)
    status = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)