from aiogram import Router
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command

from sqlalchemy import select, func, text
from datetime import datetime, timedelta

from backend.app.db.session import async_session
from backend.app.db.models import User, Payment
from backend.bot.bot import bot

ADMIN_ID = 5793624035

router = Router()

PAGE_SIZE = 20


def is_admin(message: Message):
    return message.from_user.id == ADMIN_ID


# -------------------------------------------------------
# /admin — show admin menu
# -------------------------------------------------------
@router.message(Command("admin"))
async def admin_menu(message: Message):

    if not is_admin(message):
        return await message.answer("❌ You are not authorized.")

    text = (
        "🛠 <b>Admin Panel</b>\n\n"
        "Commands:\n"
        "• /users — View users list\n"
        "• /broadcast — Send message to all users\n"
        "• /extend — Extend user plan\n"
        "• /remove — Remove a user\n"
        "• /revenue — Total revenue\n"
        "• /revenue_month — This month revenue\n"
        "• /revenue_summary — Revenue history\n"
    )

    await message.answer(text, parse_mode="HTML")


# -------------------------------------------------------
# FEATURE A: USERS LIST (PAGINATION)
# -------------------------------------------------------
@router.message(Command("users"))
async def users_main_menu(message: Message):

    if not is_admin(message):
        return await message.answer("❌ You are not authorized.")

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🟢 Active Users", callback_data="users_active_0")],
            [InlineKeyboardButton(text="🔴 Expired Users", callback_data="users_expired_0")],
        ]
    )

    await message.answer("Select a category:", reply_markup=keyboard)


@router.callback_query(lambda c: c.data.startswith("users_"))
async def users_pagination(callback):

    if callback.from_user.id != ADMIN_ID:
        return await callback.answer("Not allowed", show_alert=True)

    _, mode, page = callback.data.split("_")
    page = int(page)

    async with async_session() as session:

        if mode == "active":
            query = select(User).where(User.status == "active")
        else:
            query = select(User).where(User.status != "active")

        all_users = (await session.execute(query)).scalars().all()

    start = page * PAGE_SIZE
    end = start + PAGE_SIZE
    chunk = all_users[start:end]

    total_pages = (len(all_users) - 1) // PAGE_SIZE + 1 if all_users else 1

    text = f"📄 <b>{mode.capitalize()} Users — Page {page+1}/{total_pages}</b>\n\n"

    if not chunk:
        text += "No users found."
    else:
        for u in chunk:
            text += f"• {u.telegram_id} — {u.plan_id}\n"

    buttons = []

    if page > 0:
        buttons.append(InlineKeyboardButton(
            text="◀ Prev",
            callback_data=f"users_{mode}_{page-1}"
        ))

    if end < len(all_users):
        buttons.append(InlineKeyboardButton(
            text="Next ▶",
            callback_data=f"users_{mode}_{page+1}"
        ))

    keyboard = InlineKeyboardMarkup(inline_keyboard=[buttons] if buttons else [])

    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    await callback.answer()


# -------------------------------------------------------
# FEATURE B: BROADCAST MESSAGE
# -------------------------------------------------------
@router.message(Command("broadcast"))
async def broadcast(message: Message):

    if not is_admin(message):
        return

    args = message.text.split(" ", 1)

    if len(args) < 2:
        return await message.answer(
            "📢 Usage:\n<b>/broadcast Your message here</b>",
            parse_mode="HTML"
        )

    text_to_send = args[1]

    await message.answer("⏳ Sending broadcast...")

    async with async_session() as session:
        users = (await session.execute(select(User.telegram_id))).scalars().all()

    sent = 0
    failed = 0

    for uid in users:
        try:
            await bot.send_message(uid, text_to_send)
            sent += 1
        except:
            failed += 1

    await message.answer(
        f"📢 <b>Broadcast Complete</b>\n\n"
        f"✅ Sent: {sent}\n"
        f"❌ Failed: {failed}",
        parse_mode="HTML"
    )


# -------------------------------------------------------
# FEATURE C: REVENUE — TOTAL
# -------------------------------------------------------
@router.message(Command("revenue")))
async def revenue(message: Message):

    if not is_admin(message):
        return

    async with async_session() as session:

        total = (await session.execute(
            select(func.sum(Payment.amount)).where(Payment.status == "paid")
        )).scalar() or 0

    await message.answer(f"💰 <b>Total Revenue:</b> ₹{total}", parse_mode="HTML")


# -------------------------------------------------------
# FEATURE C2: MONTHLY REVENUE
# -------------------------------------------------------
@router.message(Command("revenue_month"))
async def revenue_month(message: Message):

    if not is_admin(message):
        return

    async with async_session() as session:

        total = (await session.execute(
            select(func.sum(Payment.amount)).where(
                Payment.status == "paid",
                func.date_trunc("month", Payment.created_at)
                == func.date_trunc("month", func.now())
            )
        )).scalar() or 0

    await message.answer(
        f"📆 <b>Revenue This Month:</b> ₹{total}",
        parse_mode="HTML"
    )


# -------------------------------------------------------
# FEATURE C3: MONTHLY REVENUE SUMMARY
# -------------------------------------------------------
@router.message(Command("revenue_summary"))
async def revenue_summary(message: Message):

    if not is_admin(message):
        return

    async with async_session() as session:

        rows = await session.execute(
            text("""
            SELECT DATE_TRUNC('month', created_at) AS month,
                   SUM(amount) AS total
            FROM payments
            WHERE status = 'paid'
            GROUP BY month
            ORDER BY month DESC;
            """)
        )

        data = rows.fetchall()

    if not data:
        return await message.answer("No payment history found.")

    msg = "📅 <b>Monthly Revenue Summary:</b>\n\n"

    for month, total in data:
        formatted = month.strftime("%B %Y")
        msg += f"• {formatted}: ₹{total}\n"

    await message.answer(msg, parse_mode="HTML")


# -------------------------------------------------------
# FEATURE D: EXTEND USER ACCESS
# -------------------------------------------------------
@router.message(Command("extend"))
async def extend_user(message: Message):

    if not is_admin(message):
        return

    parts = message.text.split()

    if len(parts) != 3:
        return await message.answer(
            "Usage:\n/extend <telegram_id> <days>", parse_mode="HTML"
        )

    tg_id = parts[1]
    days = int(parts[2])

    async with async_session() as session:

        result = await session.execute(select(User).where(User.telegram_id == tg_id))
        user = result.scalar_one_or_none()

        if not user:
            return await message.answer("❌ User not found")

        if user.expiry_date and user.expiry_date > datetime.utcnow():
            user.expiry_date += timedelta(days=days)
        else:
            user.expiry_date = datetime.utcnow() + timedelta(days=days)

        user.status = "active"

        await session.commit()

    await message.answer(
        f"✅ Extended {tg_id} by {days} days.\nNew Expiry: {user.expiry_date}",
        parse_mode="HTML"
    )

    try:
        await bot.send_message(
            tg_id,
            f"🎉 Your plan has been extended by {days} days!\n"
            f"New expiry: {user.expiry_date.strftime('%d-%m-%Y')}"
        )
    except:
        pass


# -------------------------------------------------------
# FEATURE D2: REMOVE USER
# -------------------------------------------------------
@router.message(Command("remove"))
async def remove_user(message: Message):

    if not is_admin(message):
        return

    parts = message.text.split()

    if len(parts) != 2:
        return await message.answer("Usage:\n/remove <telegram_id>", parse_mode="HTML")

    tg_id = parts[1]

    async with async_session() as session:

        result = await session.execute(select(User).where(User.telegram_id == tg_id))
        user = result.scalar_one_or_none()

        if not user:
            return await message.answer("❌ User not found")

        user.status = "inactive"
        user.expiry_date = datetime.utcnow()

        await session.commit()

    await message.answer(f"🗑 User {tg_id} removed.", parse_mode="HTML")

    try:
        await bot.send_message(
            tg_id, "❌ Your access has been removed by admin."
        )
    except:
        pass
