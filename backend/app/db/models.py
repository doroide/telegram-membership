from sqlalchemy import Column, Integer, Text, Boolean, DateTime
from sqlalchemy.sql import func
from backend.app.db.base import Base   # ✅ FIXED IMPORT


class User(Base):
    __tablename__ = "users"
#samiksh
    id = Column(Integer, primary_key=True, autoincrement=True)

    # TELEGRAM ID stored as TEXT (correct)
    telegram_id = Column(Text, nullable=False, unique=True)

    telegram_username = Column(Text, nullable=True)

    plan_id = Column(Text, nullable=True)
    razorpay_payment_id = Column(Text, nullable=True)
    status = Column(Text, nullable=True, default="active")

    start_date = Column(DateTime, nullable=True)
    expiry_date = Column(DateTime, nullable=True)
    next_renewal = Column(DateTime, nullable=True)
    payment_method = Column(Text, nullable=True)

    attempts_failed = Column(Integer, default=0)
    reminded_3d = Column(Boolean, default=False)
    reminded_1d = Column(Boolean, default=False)

    created_at = Column(DateTime, default=func.now())


from sqlalchemy import Column, Integer, Text, DateTime, ForeignKey
from sqlalchemy.sql import func


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    razorpay_payment_id = Column(Text, nullable=False)
    amount = Column(Integer, nullable=False)
    plan_id = Column(Text, nullable=True)

    status = Column(Text, nullable=True)

    created_at = Column(DateTime, default=func.now())

