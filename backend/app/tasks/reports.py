import os
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, func

from backend.app.db.session import async_session
from backend.app.db.models import User, Payment, Membership, Channel
from backend.bot.bot import bot


# =========================
# CONFIG
# =========================

ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x]

IST = timezone(timedelta(hours=5, minutes=30))


# =========================
# HELPERS
# =========================

async def _send_to_admins(text: str):
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text)
        except Exception as e:
            print(f"❌ Failed to send report to {admin_id}: {e}")


async def _all_channels_revenue(session, start, end):
    rows = await session.execute(
        select(
            Channel.name,
            func.coalesce(func.sum(Payment.amount), 0)
        )
        .outerjoin(
            Payment,
            (Payment.channel_id == Channel.id)
            & (Payment.status == "captured")
            & (Payment.created_at >= start)
            & (Payment.created_at < end)
        )
        .group_by(Channel.name)
        .order_by(func.coalesce(func.sum(Payment.amount), 0).desc())
    )
    return rows.all()


# =========================
# DAILY REPORT (YESTERDAY)
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

        change = ((revenue - prev_revenue) / prev_revenue * 100) if prev_revenue else 0

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

        channels = await _all_channels_revenue(session, start, end)

    date_label = start.astimezone(IST).strftime("%d %b")

    channel_text = "\n".join(
        f"• {name} – ₹{int(amount)}" for name, amount in channels
    ) or "• No channels"

    msg = (
        f"📊 <b>Daily Report ({date_label})</b>\n\n"
        f"💰 Revenue: ₹{int(revenue)}\n"
        f"📈 Change vs prev day: {change:+.1f}%\n\n"
        f"🆕 New users: {new_users}\n"
        f"🆕 New subs: {new_subs}\n\n"
        f"❌ Expired subs: {expired}\n"
        f"❌ Failed payments: {failed}\n\n"
        f"📺 <b>Channel-wise Revenue:</b>\n{channel_text}\n\n"
        f"✅ Active subs: {active}"
    )

    await _send_to_admins(msg)


# =========================
# WEEKLY REPORT (LAST 7 DAYS)
# =========================

async def send_weekly_report():
    now = datetime.now(timezone.utc)

    end = datetime.combine(now.date(), datetime.min.time(), tzinfo=timezone.utc)
    start = end - timedelta(days=7)

    prev_start = start - timedelta(days=7)
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

        channels = await _all_channels_revenue(session, start, end)

    range_label = f"{start.astimezone(IST):%d %b} – {(end - timedelta(days=1)).astimezone(IST):%d %b}"

    channel_text = "\n".join(
        f"• {name} – ₹{int(amount)}" for name, amount in channels
    ) or "• No channels"

    msg = (
        f"📊 <b>Weekly Summary ({range_label})</b>\n\n"
        f"💰 Revenue: ₹{int(revenue)}\n"
        f"📈 Change vs prev week: {change:+.1f}%\n\n"
        f"🆕 New users: {users}\n"
        f"🆕 New subs: {subs}\n\n"
        f"❌ Expired subs: {expired}\n"
        f"❌ Failed payments: {failed}\n\n"
        f"📺 <b>Channel-wise Revenue:</b>\n{channel_text}\n\n"
        f"✅ Active subs: {active}"
    )

    await _send_to_admins(msg)


# =========================
# MONTHLY REPORT (PREVIOUS MONTH)
# =========================

async def send_monthly_report():
    now = datetime.now(timezone.utc)

    first_this_month = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
    end = first_this_month
    start = (first_this_month - timedelta(days=1)).replace(day=1)

    prev_start = (start - timedelta(days=1)).replace(day=1)
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
                   Membership.expiry_date > end)
        )

        channels = await _all_channels_revenue(session, start, end)

    month_label = start.astimezone(IST).strftime("%b %Y")

    channel_text = "\n".join(
        f"• {name} – ₹{int(amount)}" for name, amount in channels
    ) or "• No channels"

    msg = (
        f"📊 <b>Monthly Summary ({month_label})</b>\n\n"
        f"💰 Revenue: ₹{int(revenue)}\n"
        f"📈 Change vs prev month: {change:+.1f}%\n\n"
        f"🆕 New users: {users}\n"
        f"🆕 New subs: {subs}\n\n"
        f"❌ Expired subs: {expired}\n"
        f"❌ Failed payments: {failed}\n\n"
        f"📺 <b>Channel-wise Revenue:</b>\n{channel_text}\n\n"
        f"✅ Active subs (month end): {active}"
    )

    await _send_to_admins(msg)


# =========================
# YEARLY REPORT (PREVIOUS YEAR)
# =========================

async def send_yearly_report():
    now = datetime.now(timezone.utc)

    start = datetime(now.year - 1, 1, 1, tzinfo=timezone.utc)
    end = datetime(now.year, 1, 1, tzinfo=timezone.utc)

    prev_start = datetime(now.year - 2, 1, 1, tzinfo=timezone.utc)
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
                   Membership.expiry_date > end)
        )

        channels = await _all_channels_revenue(session, start, end)

    channel_text = "\n".join(
        f"• {name} – ₹{int(amount)}" for name, amount in channels
    ) or "• No channels"

    msg = (
        f"📊 <b>Yearly Summary ({start.year})</b>\n\n"
        f"💰 Revenue: ₹{int(revenue)}\n"
        f"📈 Change vs prev year: {change:+.1f}%\n\n"
        f"🆕 New users: {users}\n"
        f"🆕 New subs: {subs}\n\n"
        f"❌ Expired subs: {expired}\n"
        f"❌ Failed payments: {failed}\n\n"
        f"📺 <b>Channel-wise Revenue:</b>\n{channel_text}\n\n"
        f"✅ Active subs (year end): {active}"
    )

    await _send_to_admins(msg)
