from datetime import datetime, timedelta

from sqlalchemy import select

from backend.app.db.models import Membership, User, Channel


class MembershipService:

    # ============================================
    # PLAN → DAYS mapping
    # ============================================

    PLAN_DAYS = {
        "1m": 30,
        "3m": 90,
        "6m": 180,
        "12m": 365,
        "lifetime": 36500
    }

    # ============================================
    # Handle successful Razorpay payment
    # ============================================

    @staticmethod
    async def handle_successful_payment(session, user_id: int, plan_id: str, amount: float):

        days = MembershipService.PLAN_DAYS.get(plan_id, 30)

        now = datetime.utcnow()
        new_expiry = now + timedelta(days=days)

        # ----------------------------------------
        # update user's total spent
        # ----------------------------------------

        user = await session.get(User, user_id)

        if user:
            user.total_spent += amount

        # ----------------------------------------
        # find active membership
        # ----------------------------------------

        result = await session.execute(
            select(Membership).where(
                Membership.user_id == user_id,
                Membership.is_active == True
            )
        )

        membership = result.scalar_one_or_none()

        # ----------------------------------------
        # extend or create
        # ----------------------------------------

        if membership:
            # extend from current expiry if future
            base_date = max(membership.expiry_date, now)
            membership.expiry_date = base_date + timedelta(days=days)

        else:
            membership = Membership(
                user_id=user_id,
                channel_id=None,  # can be assigned later
                plan=plan_id,
                start_date=now,
                expiry_date=new_expiry,
                is_active=True
            )
            session.add(membership)
