import os
from datetime import datetime, timedelta, timezone, date
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command

router = Router()

ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x]
IST = timezone(timedelta(hours=5, minutes=30))


def _nav_keyboard(report_date: date) -> InlineKeyboardMarkup:
    """Build Previous / Next day navigation buttons."""
    today = datetime.now(timezone.utc).date()
    yesterday = today - timedelta(days=1)

    prev_date = report_date - timedelta(days=1)
    next_date = report_date + timedelta(days=1)

    rows = []

    nav_row = []
    nav_row.append(InlineKeyboardButton(
        text="⬅️ Prev Day",
        callback_data=f"dreport_{prev_date.isoformat()}"
    ))
    if next_date <= yesterday:
        nav_row.append(InlineKeyboardButton(
            text="Next Day ➡️",
            callback_data=f"dreport_{next_date.isoformat()}"
        ))
    else:
        # Already on latest day — show disabled label
        nav_row.append(InlineKeyboardButton(
            text="Next Day ➡️",
            callback_data="dreport_noop"
        ))

    rows.append(nav_row)
    rows.append([InlineKeyboardButton(
        text="📅 Jump to Yesterday",
        callback_data=f"dreport_{yesterday.isoformat()}"
    )])

    return InlineKeyboardMarkup(inline_keyboard=rows)


# =====================================================
# /DAILYREPORT COMMAND
# =====================================================

@router.message(Command("dailyreport"))
async def dailyreport_command(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔ Admin only.")
        return

    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).date()
    await _send_report_for_date(message, yesterday, edit=False)


# =====================================================
# NAVIGATION CALLBACKS
# =====================================================

@router.callback_query(F.data.startswith("dreport_"))
async def navigate_report(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Admin only.", show_alert=True)
        return

    date_str = callback.data.split("_")[1]

    if date_str == "noop":
        await callback.answer("Already on latest day.", show_alert=True)
        return

    try:
        report_date = date.fromisoformat(date_str)
    except ValueError:
        await callback.answer("Invalid date.", show_alert=True)
        return

    try:
        await callback.answer()
    except Exception:
        pass

    await _send_report_for_date(callback.message, report_date, edit=True)


# =====================================================
# CORE: BUILD AND SEND REPORT FOR A DATE
# =====================================================

async def _send_report_for_date(message, report_date: date, edit: bool = False):
    from backend.app.tasks.reports import send_member_daily_report
    from backend.app.db.session import async_session
    from backend.app.db.models import Membership, User, Channel
    from sqlalchemy import select

    start = datetime.combine(report_date, datetime.min.time(), tzinfo=timezone.utc)
    end = start + timedelta(days=1)

    today_start = datetime.combine(datetime.now(timezone.utc).date(), datetime.min.time(), tzinfo=timezone.utc)
    today_end = today_start + timedelta(days=1)

    async with async_session() as session:

        # New members on report_date
        new_result = await session.execute(
            select(Membership, User, Channel)
            .join(User, Membership.user_id == User.id)
            .join(Channel, Membership.channel_id == Channel.id)
            .where(Membership.created_at.between(start, end))
            .order_by(Membership.created_at.desc())
        )
        new_members = new_result.all()

        # Expiring on report_date
        expiring_result = await session.execute(
            select(Membership, User, Channel)
            .join(User, Membership.user_id == User.id)
            .join(Channel, Membership.channel_id == Channel.id)
            .where(
                Membership.is_active == True,
                Membership.expiry_date.between(start, end)
            )
            .order_by(Membership.expiry_date.asc())
        )
        expiring = expiring_result.all()

        # Expired on report_date
        expired_result = await session.execute(
            select(Membership, User, Channel)
            .join(User, Membership.user_id == User.id)
            .join(Channel, Membership.channel_id == Channel.id)
            .where(Membership.expiry_date.between(start, end))
            .order_by(Membership.expiry_date.desc())
        )
        expired = expired_result.all()

    date_label = start.astimezone(IST).strftime("%d %b %Y")

    msg = (
        f"👥 <b>Member Report — {date_label}</b>\n"
        f"📊 {len(new_members)} new | {len(expiring)} expiring | {len(expired)} expired\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
    )

    message_buttons = []

    # New Members
    if new_members:
        msg += "🆕 <b>NEW MEMBERS</b>\n\n"
        for idx, (m, u, ch) in enumerate(new_members, 1):
            name = u.full_name or "No Name"
            username = f"@{u.username}" if u.username else "No username"
            msg += (
                f"{idx}. <b>{name}</b> ({username})\n"
                f"   📺 {ch.name} | ₹{int(m.amount_paid)} | {m.validity_days}d\n\n"
            )
            message_buttons.append(InlineKeyboardButton(
                text=f"💬 {name}",
                url=f"tg://user?id={u.telegram_id}"
            ))
        msg += "━━━━━━━━━━━━━━━━━━━━\n\n"
    else:
        msg += "🆕 <b>NEW MEMBERS</b>\nNone\n━━━━━━━━━━━━━━━━━━━━\n\n"

    # Expiring
    if expiring:
        msg += "⚠️ <b>EXPIRING</b>\n\n"
        for idx, (m, u, ch) in enumerate(expiring, 1):
            name = u.full_name or "No Name"
            username = f"@{u.username}" if u.username else "No username"
            expiry_time = m.expiry_date.astimezone(IST).strftime("%I:%M %p")
            msg += (
                f"{idx}. <b>{name}</b> ({username})\n"
                f"   📺 {ch.name} | Expires at {expiry_time} IST\n\n"
            )
            message_buttons.append(InlineKeyboardButton(
                text=f"💬 {name}",
                url=f"tg://user?id={u.telegram_id}"
            ))
        msg += "━━━━━━━━━━━━━━━━━━━━\n\n"
    else:
        msg += "⚠️ <b>EXPIRING</b>\nNone\n━━━━━━━━━━━━━━━━━━━━\n\n"

    # Expired
    if expired:
        msg += "❌ <b>EXPIRED</b>\n\n"
        for idx, (m, u, ch) in enumerate(expired, 1):
            name = u.full_name or "No Name"
            username = f"@{u.username}" if u.username else "No username"
            expiry_time = m.expiry_date.astimezone(IST).strftime("%I:%M %p")
            msg += (
                f"{idx}. <b>{name}</b> ({username})\n"
                f"   📺 {ch.name} | Expired at {expiry_time} IST\n\n"
            )
            message_buttons.append(InlineKeyboardButton(
                text=f"💬 {name}",
                url=f"tg://user?id={u.telegram_id}"
            ))
    else:
        msg += "❌ <b>EXPIRED</b>\nNone\n"

    # Build keyboard — message buttons 2 per row + nav at bottom
    keyboard_rows = [
        message_buttons[i:i+2] for i in range(0, len(message_buttons), 2)
    ]
    # Add nav buttons at bottom
    nav = _nav_keyboard(report_date)
    for row in nav.inline_keyboard:
        keyboard_rows.append(row)

    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

    try:
        if edit:
            await message.edit_text(msg, parse_mode="HTML", reply_markup=reply_markup)
        else:
            await message.answer(msg, parse_mode="HTML", reply_markup=reply_markup)
    except Exception as e:
        # Message too long — split
        await message.answer(msg[:4000], parse_mode="HTML", reply_markup=reply_markup)