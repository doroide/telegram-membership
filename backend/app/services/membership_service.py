from datetime import datetime, timedelta
from sqlalchemy import select

from backend.app.db.models import Membership, Payment, User
from backend.app.services.tier_service import TierService


PLAN_DAYS = {
    "1m": 30,
    "3m": 90,
    "6m": 180,
    "12m": 365,
    "lifetime": None
}


class MembershipService:

    # =====================================================
    # Calculate expiry from plan
    # =====================================================

    @staticmethod
    def calculate_expiry(plan: str):
        if plan == "lifetime":
            return None

        days = PLAN_DAYS.get(plan, 30)
        return datetime.utcnow() + timedelta(days=days)

    # =====================================================
    # Create membership (new or renewal)
    # =====================================================

    @staticmethod
    async def create_membership(
        session,
        user_id: int,
        channel_id: int,
        plan: str,
        amount: float
    ):
        expiry = MembershipService.calculate_expiry(plan)

        membership = Membership(
            user_id=user_id,
            channel_id=channel_id,
            plan=plan,
            expiry_date=expiry
        )

        session.add(membership)
        await session.flush()

        # record payment
        payment = Payment(
            user_id=user_id,
            amount=amount,
            status="success",
            membership_id=membership.id
        )

        session.add(payment)

        # update user total spent
        user = await session.get(User, user_id)
        user.total_spent = (user.total_spent or 0) + amount

        # update tier automatically
        user.tier = TierService.get_tier(user.total_spent)

        await session.commit()

        return membership

    # =====================================================
    # Extend existing membership (renewal)
    # =====================================================

    @staticmethod
    async def extend_membership(session, membership: Membership, plan: str, amount: float):

        if plan != "lifetime":
            days = PLAN_DAYS[plan]

            base = membership.expiry_date or datetime.utcnow()
            membership.expiry_date = base + timedelta(days=days)

        membership.is_active = True

        # payment
        payment = Payment(
            user_id=membership.user_id,
            amount=amount,
            status="success",
            membership_id=membership.id
        )
        session.add(payment)

        await session.commit()

    # =====================================================
    # Get expired memberships
    # =====================================================

    @staticmethod
    async def get_expired(session):
        now = datetime.utcnow()

        result = await session.execute(
            select(Membership).where(
                Membership.is_active == True,
                Membership.expiry_date != None,
                Membership.expiry_date < now
            )
        )

        return result.scalars().all()

    # =====================================================
    # Deactivate membership
    # =====================================================

    @staticmethod
    async def deactivate(session, membership: Membership):
        membership.is_active = False
        await session.commit()
