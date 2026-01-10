from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command

from sqlalchemy import select, func

from backend.app.db.session import async_session
from backend.app.db.models import User

ADMIN_ID = 5793624035  # update if needed

router = Router()


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
        "Available commands:\n"
        "• /stats — User statistics\n"
        "• /revenue — Total revenue\n"
        "• /revenue_month — Monthly revenue\n"
        "• /revenue_summary — Revenue history\n"
        "• /extend — Extend a user's plan\n"
        "• /remove — Remove a user\n"
        "• /broadcast — Send message to all users\n"
    )

    await message.answer(text, parse_mode="HTML")


# -------------------------------------------------------
# /stats — basic system stats
# -------------------------------------------------------
@router.message(Command("stats"))
async def stats(message: Message):

    if not is_admin(message):
        return

    async with async_session() as session:

        total_users = (await session.execute(
            select(func.count()).select_from(User)
        )).scalar()

        active_users = (await session.execute(
            select(func.count()).select_from(User).where(User.status == "active")
        )).scalar()

        inactive_users = (await session.execute(
            select(func.count()).select_from(User).where(User.status == "inactive")
        )).scalar()

    await message.answer(
        f"📊 <b>Bot Stats</b>\n\n"
        f"👤 Total users: <b>{total_users}</b>\n"
        f"🟢 Active: <b>{active_users}</b>\n"
        f"🔴 Inactive: <b>{inactive_users}</b>",
        parse_mode="HTML"
    )


# -------------------------------------------------------
# /revenue — total revenue collected
# -------------------------------------------------------
@router.message(Command("revenue"))
async def revenue(message: Message):

    if not is_admin(message):
        return

    async with async_session() as session:

        total = (await session.execute(
            select(func.sum(Payment.amount)).where(Payment.status == "paid")
        )).scalar()

        if total is None:
            total = 0

    await message.answer(
        f"💰 <b>Total Revenue:</b> ₹{total}",
        parse_mode="HTML"
    )


# -------------------------------------------------------
# /revenue_month — revenue for current month
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
# /revenue_summary — monthly revenue breakdown
# -------------------------------------------------------
@router.message(Command("revenue_summary"))
async def revenue_summary(message: Message):

    if not is_admin(message):
        return

    async with async_session() as session:

        rows = await session.execute(
            """
            SELECT DATE_TRUNC('month', created_at) AS month,
                   SUM(amount) AS total
            FROM payments
            WHERE status = 'paid'
            GROUP BY month
            ORDER BY month DESC;
            """
        )

        data = rows.fetchall()

    if not data:
        return await message.answer("No payment history found.")

    msg = "📆 <b>Monthly Revenue Summary:</b>\n\n"

    for month, total in data:
        formatted = month.strftime("%B %Y")
        msg += f"• {formatted}: ₹{total}\n"

    await message.answer(msg, parse_mode="HTML")
