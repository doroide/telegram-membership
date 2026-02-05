from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command

from sqlalchemy import select, func
from datetime import datetime

from backend.app.db.session import async_session
from backend.app.db.models import User, Membership, Channel


router = Router()


# =====================================================
# /stats
# =====================================================
@router.message(Command("stats"))
async def stats_handler(message: Message):

    # 👉 OPTIONAL: restrict to only you
    ADMIN_ID = 123456789  # replace with your telegram id
    if message.from_user.id != ADMIN_ID:
        return

    now = datetime.utcnow()

    start_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    start_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    if now.month == 1:
        last_month = now.replace(year=now.year - 1, month=12, day=1)
    else:
        last_month = now.replace(month=now.month - 1, day=1)

    last_month_start = last_month.replace(hour=0, minute=0, second=0, microsecond=0)
    last_month_end = start_month

    async with async_session() as session:

        # ==============================
        # USERS
        # ==============================
        total_users = await session.scalar(
            select(func.count(User.id))
        )

        active_memberships = await session.scalar(
            select(func.count(Membership.id)).where(
                Membership.is_active == True,
                Membership.expiry_date > now
            )
        )

        # ==============================
        # REVENUE
        # ==============================
        today_rev = await session.scalar(
            select(func.coalesce(func.sum(Membership.amount_paid), 0))
            .where(Membership.created_at >= start_today)
        )

        month_rev = await session.scalar(
            select(func.coalesce(func.sum(Membership.amount_paid), 0))
            .where(Membership.created_at >= start_month)
        )

        last_month_rev = await session.scalar(
            select(func.coalesce(func.sum(Membership.amount_paid), 0))
            .where(
                Membership.created_at >= last_month_start,
                Membership.created_at < last_month_end
            )
        )

        all_time_rev = await session.scalar(
            select(func.coalesce(func.sum(Membership.amount_paid), 0))
        )

        # ==============================
        # CHANNEL-WISE
        # ==============================
        result = await session.execute(
            select(
                Channel.name,
                func.sum(Membership.amount_paid)
            )
            .join(Membership)
            .group_by(Channel.name)
        )

        channel_rows = result.all()

    # ==============================
    # BUILD MESSAGE
    # ==============================
    text = (
        f"📊 <b>BOT STATS</b>\n\n"
        f"👥 Total Users: {total_users}\n"
        f"✅ Active Memberships: {active_memberships}\n\n"
        f"💰 <b>Revenue</b>\n"
        f"Today: ₹{today_rev}\n"
        f"This Month: ₹{month_rev}\n"
        f"Last Month: ₹{last_month_rev}\n"
        f"All Time: ₹{all_time_rev}\n\n"
        f"📺 <b>Channel Revenue</b>\n"
    )

    for name, revenue in channel_rows:
        text += f"{name} → ₹{revenue or 0}\n"

    await message.answer(text)
