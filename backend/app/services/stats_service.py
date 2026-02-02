from datetime import datetime
from sqlalchemy import select, func

from backend.app.db.models import Payment, Membership


class StatsService:

    @staticmethod
    async def today_revenue(session):
        today = datetime.utcnow().date()

        result = await session.execute(
            select(func.sum(Payment.amount)).where(
                func.date(Payment.created_at) == today
            )
        )
        return result.scalar() or 0

    @staticmethod
    async def monthly_revenue(session):
        start = datetime.utcnow().replace(day=1)

        result = await session.execute(
            select(func.sum(Payment.amount)).where(
                Payment.created_at >= start
            )
        )
        return result.scalar() or 0

    @staticmethod
    async def active_users(session):
        result = await session.execute(
            select(func.count(Membership.id)).where(
                Membership.is_active == True
            )
        )
        return result.scalar() or 0

    @staticmethod
    async def expired_users(session):
        result = await session.execute(
            select(func.count(Membership.id)).where(
                Membership.is_active == False
            )
        )
        return result.scalar() or 0
