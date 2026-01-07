from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command

from backend.app.db.session import async_session
from backend.app.db.models import User, Payment

from backend.bot.bot import bot
from sqlalchemy import func, extract

ADMIN_ID = 5793624035  # change to your real Telegram ID

router = Router()


def is_admin(message: Message):
    return message.from_user.id == ADMIN_ID


# -----------------------------------------------------
# /stats — basic stats
# -----------------------------------------------------
@router.message(Command("stats"))
async def stats(message: Message):

    if not is_admin(message):
        return

    async with async_session() as session:
        total_users = (await session.execute(func.count(User.telegram_id))).scalar()
        active_users = (await session.execute(func.count(User.telegram_id).where(User.status == "active"))).scalar()
        expired_users = (await session.execute(func.count(User.telegram_id).where(User.status == "expired"))).scalar()

    await message.answer(
        f"📊 *Bot Stats:*\n\n"
        f"👤 Total users: `{total_users}`\n"
        f"✅ Active: `{active_users}`\n"
        f"❌ Expired: `{expired_users}`",
        parse_mode="Markdown"
    )


# -----------------------------------------------------
# /revenue_month — total money received this month
# -----------------------------------------------------
@router.message(Command("revenue_month"))
async def revenue_month(message: Message):

    if not is_admin(message):
        return

    async with async_session() as session:
        current_month = func.date_trunc("month", func.now())

        total = (
            await session.execute(
                func.sum(Payment.amount).where(
                    func.date_trunc("month", Payment.created_at) == current_month
                )
            )
        ).scalar() or 0

        # Plan wise breakdown
        plan_199 = (
            await session.execute(
                func.sum(Payment.amount).where(
                    Payment.plan_id == "plan_199_4m",
                    func.date_trunc("month", Payment.created_at) == current_month
                )
            )
        ).scalar() or 0

        plan_399 = (
            await session.execute(
                func.sum(Payment.amount).where(
                    Payment.plan_id == "plan_399_3m",
                    func.date_trunc("month", Payment.created_at) == current_month
                )
            )
        ).scalar() or 0

        plan_599 = (
            await session.execute(
                func.sum(Payment.amount).where(
                    Payment.plan_id == "plan_599_6m",
                    func.date_trunc("month", Payment.created_at) == current_month
                )
            )
        ).scalar() or 0

        plan_799 = (
            await session.execute(
                func.sum(Payment.amount).where(
                    Payment.plan_id == "plan_799_12m",
                    func.date_trunc("month", Payment.created_at) == current_month
                )
            )
        ).scalar() or 0

    # Response to admin
    await message.answer(
        f"💰 *Revenue This Month*\n\n"
        f"Total: ₹{total}\n\n"
        f"📦 Plan wise:\n"
        f"• ₹199 → ₹{plan_199}\n"
        f"• ₹399 → ₹{plan_399}\n"
        f"• ₹599 → ₹{plan_599}\n"
        f"• ₹799 → ₹{plan_799}",
        parse_mode="Markdown"
    )


# -----------------------------------------------------
# /revenue_summary — monthly revenue summary
# -----------------------------------------------------
@router.message(Command("revenue_summary"))
async def revenue_summary(message: Message):

    if not is_admin(message):
        return

    async with async_session() as session:
        rows = await session.execute(
            func.date_trunc("month", Payment.created_at).label("month"),
            func.sum(Payment.amount).label("total")
        )

        rows = await session.execute(
            """
            SELECT DATE_TRUNC('month', created_at) AS month,
                   SUM(amount) AS total
            FROM payments
            GROUP BY month
            ORDER BY month DESC;
            """
        )

        data = rows.fetchall()

    if not data:
        await message.answer("No payment data found.")
        return

    msg = "📆 *Monthly Revenue Summary:*\n\n"

    for month, total in data:
        month_str = month.strftime("%B %Y")
        msg += f"• {month_str}: ₹{total}\n"

    await message.answer(msg, parse_mode="Markdown")
