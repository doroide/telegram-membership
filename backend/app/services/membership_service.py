from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import select

from backend.app.db.models import Membership, User, Channel
from backend.bot.bot import bot


class MembershipService:

    PLAN_DAYS = {
        "1m": 30,
        "3m": 90,
        "6m": 180,
        "12m": 365,
        "lifetime": 36500
    }

    @staticmethod
    async def handle_successful_payment(session, user_id: int, plan_id: str, amount: float):

        # ✅ ALWAYS convert money to Decimal
        amount = Decimal(str(amount))

        days = MembershipService.PLAN_DAYS.get(plan_id, 30)

        now = datetime.utcnow()
        new_expiry = now + timedelta(days=days)

        # ------------------------------
        # Update user spend safely
        # ------------------------------
        user = await session.get(User, user_id)

        if user:
            user.total_spent = (user.total_spent or Decimal("0")) + amount

        # ------------------------------
        # Get first channel
        # ------------------------------
        result = await session.execute(select(Channel))
        channel = result.scalars().first()

        if not channel:
            print("⚠️ No channel configured")
            return

        # ------------------------------
        # Create invite link
        # ------------------------------
        invite = await bot.create_chat_invite_link(
            chat_id=channel.telegram_chat_id,
            member_limit=1
        )

        # ------------------------------
        # Membership logic
        # ------------------------------
        result = await session.execute(
            select(Membership).where(
                Membership.user_id == user_id,
                Membership.is_active == True
            )
        )

        membership = result.scalar_one_or_none()

        if membership:
            base = max(membership.expiry_date, now)
            membership.expiry_date = base + timedelta(days=days)
        else:
            membership = Membership(
                user_id=user_id,
                channel_id=channel.id,
                plan=plan_id,
                start_date=now,
                expiry_date=new_expiry,
                is_active=True
            )
            session.add(membership)

        # ------------------------------
        # Send invite
        # ------------------------------
        await bot.send_message(
            user_id,
            f"✅ Payment successful!\n\nHere is your access:\n{invite.invite_link}"
        )
