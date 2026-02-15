import os
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, func, desc

from backend.app.db.session import async_session
from backend.app.db.models import User, Payment, Membership, Channel
from backend.bot.bot import bot

ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x]

IST = timezone(timedelta(hours=5, minutes=30))


# =========================
# SHARED HELPERS
# =========================

async def _send_to_admins(text: str):
    for admin in ADMIN_IDS:
        try:
            await bot.send_message(admin, text)
        except Exception as e:
            print(f"❌ Admin send failed {admin}: {e}")


async def _top_channels(session, start, end):
    rows = await session.execute(
        select(Channel.name, func.sum(Payment.amount))
        .join(Payment, Payment.channel_id == Channel.id)
        .where(
            Payment.status == "captured",
            Payment.created_at >= start,
            Payment.created_at < end
        )
        .group_by(Channel.name)
        .order_by(desc(func.sum(Payment.amount)))
        .limit(3)
    )
    return rows.all()


# =========================
# DAILY REPORT
# =========================

async def send_daily_report():
    now = datetime.now(timezone.utc)
    report_day = now.date() - timedelta(days=1)

    start = datetime.combine(report_day, datetime.min.time(), tzinfo=timezone.utc)
    end = start + timedelta(days=1)

    prev_start = start - timedelta(days=1)
    prev_end = start

    async with async_session() as session:

        revenue = await session.scalar(
            select(func.coalesce(func.sum(Payment.amount), 0))
            .where(Payment.status == "captured",
                   Payment.created_at.between(start, end))
        )

        prev_revenue = await session.scalar(
            select(func.coalesce(func.sum(Payment.amount), 0))
            .where(Payment.status == "captured",
                   Payment.created_at.between(prev_start, prev_end))
        )

        revenue_change = (
            ((revenue - prev_revenue) / prev_revenue * 100)
            if prev_revenue else 0
        )

        new_users = await session.scalar(
            select(func.count(User.id))
            .where(User.created_at.between(start, end))
        )

        new_subs = await session.scalar(
            select(func.count(Membership.id))
            .where(Membership.created_at.between(start, end))
        )

        expired = await session.scalar(
            select(func.count(Membership.id))
            .where(Membership.expiry_date.between(start, end))
        )

        failed_payments = await session.scalar(
            select(func.count(Payment.id))
            .where(Payment.status == "failed",
                   Payment.created_at.between(start, end))
        )

        active_subs = await session.scalar(
            select(func.count(Membership.id))
            .where(Membership.is_active == True,
                   Membership.expiry_date > now)
        )

        top_channels = await _top_channels(session, start, end)

    date_str = datetime.combine(report_day, datetime.min.time(), tzinfo=timezone.utc)\
        .astimezone(IST).strftime("%d %b")

    channel_text = "\n".join(
        f"• {name} – ₹{int(amount)}" for name, amount in top_channels
    ) or "• No sales"

    msg = (
        f"📊 <b>Daily Report ({date_str})</b>\n\n"
        f"💰 Revenue: ₹{int(revenue)}\n"
        f"📈 Change vs prev day: {revenue_change:+.1f}%\n\n"
        f"🆕 New users: {new_users}\n"
        f"🆕 New subs: {new_subs}\n\n"
        f"❌ Expired subs: {expired}\n"
        f"❌ Failed payments: {failed_payments}\n\n"
        f"📺 <b>Top Channels:</b>\n{channel_text}\n\n"
        f"✅ Active subs: {active_subs}"
    )

    await _send_to_admins(msg)


# =========================
# WEEKLY REPORT
# =========================

async def send_weekly_report():
    now = datetime.now(timezone.utc)
    end = datetime.combine(now.date(), datetime.min.time(), tzinfo=timezone.utc)
    start = end - timedelta(days=7)
    prev_start = start - timedelta(days=7)

    async with async_session() as session:

        revenue = await session.scalar(
            select(func.sum(Payment.amount))
            .where(Payment.status == "captured",
                   Payment.created_at.between(start, end))
        ) or 0

        prev_revenue = await session.scalar(
            select(func.sum(Payment.amount))
            .where(Payment.status == "captured",
                   Payment.created_at.between(prev_start, start))
        ) or 0

        change = ((revenue - prev_revenue) / prev_revenue * 100) if prev_revenue else 0

        users = await session.scalar(
            select(func.count(User.id))
            .where(User.created_at.between(start, end))
        )

        subs = await session.scalar(
            select(func.count(Membership.id))
            .where(Membership.created_at.between(start, end))
        )

        expired = await session.scalar(
            select(func.count(Membership.id))
            .where(Membership.expiry_date.between(start, end))
        )

        failed = await session.scalar(
            select(func.count(Payment.id))
            .where(Payment.status == "failed",
                   Payment.created_at.between(start, end))
        )

        active = await session.scalar(
            select(func.count(Membership.id))
            .where(Membership.is_active == True,
                   Membership.expiry_date > now)
        )

        top_channels = await _top_channels(session, start, end)

    range_str = f"{(start+timedelta(days=1)).astimezone(IST):%d %b} – {(end-timedelta(days=1)).astimezone(IST):%d %b}"

    channel_text = "\n".join(
        f"• {name} – ₹{int(amount)}" for name, amount in top_channels
    ) or "• No sales"

    msg = (
        f"📊 <b>Weekly Summary ({range_str})</b>\n\n"
        f"💰 Revenue: ₹{int(revenue)}\n"
        f"📈 Change vs prev week: {change:+.1f}%\n\n"
        f"🆕 New users: {users}\n"
        f"🆕 New subs: {subs}\n\n"
        f"❌ Expired subs: {expired}\n"
        f"❌ Failed payments: {failed}\n\n"
        f"📺 <b>Top Channels:</b>\n{channel_text}\n\n"
        f"✅ Active subs: {active}"
    )

    await _send_to_admins(msg)
