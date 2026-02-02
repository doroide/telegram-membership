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
# USER (existing + extended)
# =========================================================

class User(Base):
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True)  # telegram user id

    username = Column(String(255), nullable=True)
    full_name = Column(String(255), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # ✅ NEW (tier system)
    total_spent = Column(Numeric, default=0)
    tier = Column(String(20), default="Budget")

    # relationships
    memberships = relationship("Membership", back_populates="user")
    payments = relationship("Payment", back_populates="user")
    acces
