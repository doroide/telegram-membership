import os
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, func

from backend.app.db.session import async_session
from backend.app.db.models import User, Payment, Membership, Channel
from backend.bot.bot import bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

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
            await bot.send_message(admin_id, text, parse_mode="HTML")
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


# =========================
# MEMBER DAILY REPORT
# =========================

async def send_member_daily_report(date=None):
    """
    Sends member activity report for a given date.
    If date is None, uses yesterday.
    Called automatically at 9 AM and also by /dailyreport command.
    """
    now = datetime.now(timezone.utc)

    if date is None:
        report_day = now.date() - timedelta(days=1)
    else:
        report_day = date

    start = datetime.combine(report_day, datetime.min.time(), tzinfo=timezone.utc)
    end = start + timedelta(days=1)

    # Expiring today window
    today_start = datetime.combine(now.date(), datetime.min.time(), tzinfo=timezone.utc)
    today_end = today_start + timedelta(days=1)

    async with async_session() as session:

        # ── 1. New members on report_day ─────────────────────────
        new_result = await session.execute(
            select(Membership, User, Channel)
            .join(User, Membership.user_id == User.id)
            .join(Channel, Membership.channel_id == Channel.id)
            .where(Membership.created_at.between(start, end))
            .order_by(Membership.created_at.desc())
        )
        new_members = new_result.all()

        # ── 2. Expiring today ────────────────────────────────────
        expiring_result = await session.execute(
            select(Membership, User, Channel)
            .join(User, Membership.user_id == User.id)
            .join(Channel, Membership.channel_id == Channel.id)
            .where(
                Membership.is_active == True,
                Membership.expiry_date.between(today_start, today_end)
            )
            .order_by(Membership.expiry_date.asc())
        )
        expiring = expiring_result.all()

        # ── 3. Expired on report_day ─────────────────────────────
        expired_result = await session.execute(
            select(Membership, User, Channel)
            .join(User, Membership.user_id == User.id)
            .join(Channel, Membership.channel_id == Channel.id)
            .where(Membership.expiry_date.between(start, end))
            .order_by(Membership.expiry_date.desc())
        )
        expired = expired_result.all()

    date_label = start.astimezone(IST).strftime("%d %b %Y")

    # ── Summary line ─────────────────────────────────────────────
    msg = (
        f"👥 <b>Member Report — {date_label}</b>\n"
        f"📊 {len(new_members)} new | {len(expiring)} expiring today | {len(expired)} expired\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
    )

    keyboards = []

    # ── New Members ──────────────────────────────────────────────
    if new_members:
        msg += "🆕 <b>NEW MEMBERS</b>\n\n"
        for idx, (m, u, ch) in enumerate(new_members, 1):
            name = u.full_name or "No Name"
            username = f"@{u.username}" if u.username else "No username"
            msg += (
                f"{idx}. <b>{name}</b> ({username})\n"
                f"   📺 {ch.name} | ₹{int(m.amount_paid)} | {m.validity_days}d\n\n"
            )
            keyboards.append(
                InlineKeyboardButton(
                    text=f"💬 {name}",
                    url=f"tg://user?id={u.telegram_id}"
                )
            )
        msg += "━━━━━━━━━━━━━━━━━━━━\n\n"
    else:
        msg += "🆕 <b>NEW MEMBERS</b>\nNone\n━━━━━━━━━━━━━━━━━━━━\n\n"

    # ── Expiring Today ───────────────────────────────────────────
    if expiring:
        msg += "⚠️ <b>EXPIRING TODAY</b>\n\n"
        for idx, (m, u, ch) in enumerate(expiring, 1):
            name = u.full_name or "No Name"
            username = f"@{u.username}" if u.username else "No username"
            expiry_time = m.expiry_date.astimezone(IST).strftime("%I:%M %p")
            msg += (
                f"{idx}. <b>{name}</b> ({username})\n"
                f"   📺 {ch.name} | Expires at {expiry_time} IST\n\n"
            )
            keyboards.append(
                InlineKeyboardButton(
                    text=f"💬 {name}",
                    url=f"tg://user?id={u.telegram_id}"
                )
            )
        msg += "━━━━━━━━━━━━━━━━━━━━\n\n"
    else:
        msg += "⚠️ <b>EXPIRING TODAY</b>\nNone\n━━━━━━━━━━━━━━━━━━━━\n\n"

    # ── Expired Yesterday ────────────────────────────────────────
    if expired:
        msg += "❌ <b>EXPIRED</b>\n\n"
        for idx, (m, u, ch) in enumerate(expired, 1):
            name = u.full_name or "No Name"
            username = f"@{u.username}" if u.username else "No username"
            expired_time = m.expiry_date.astimezone(IST).strftime("%I:%M %p")
            msg += (
                f"{idx}. <b>{name}</b> ({username})\n"
                f"   📺 {ch.name} | Expired at {expired_time} IST\n\n"
            )
            keyboards.append(
                InlineKeyboardButton(
                    text=f"💬 {name}",
                    url=f"tg://user?id={u.telegram_id}"
                )
            )
    else:
        msg += "❌ <b>EXPIRED</b>\nNone\n"

    # ── Build keyboard — 2 buttons per row ──────────────────────
    keyboard_rows = [
        keyboards[i:i+2] for i in range(0, len(keyboards), 2)
    ]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard_rows) if keyboard_rows else None

    # ── Send to all admins ───────────────────────────────────────
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                msg,
                parse_mode="HTML",
                reply_markup=reply_markup
            )
        except Exception as e:
            print(f"❌ Failed to send member report to {admin_id}: {e}")