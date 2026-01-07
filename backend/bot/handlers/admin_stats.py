from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from backend.app.db.session import async_session
from backend.app.db.models import User, Payment
from datetime import datetime

router = Router()

# ============================
# ADMIN TELEGRAM ID (update)
# ============================
ADMIN_ID = 5793624035  # <-- replace with your Telegram ID


@router.message(Command("stats"))
async def admin_stats(message: Message):

    # Block non-admin users
    if message.from_user.id != ADMIN_ID:
        return await message.answer("❌ You are not authorized.")

    async with async_session() as session:
        # ----------- ACTIVE USERS ----------
        result_users = await session.execute(
            User.select().where(User.status == "active")
        )
        active_users = result_users.scalars().all()
        active_count = len(active_users)

        # ------------ TOTAL REVENUE -----------
        result_payments = await session.execute(Payment.select())
        payments = result_payments.scalars().all()

        total_revenue = sum(p.amount for p in payments)

        # ---------- PLAN WISE REVENUE ----------
        plan_totals = {}
        for p in payments:
            plan_totals[p.plan_id] = plan_totals.get(p.plan_id, 0) + p.amount

        plan_report = ""
        for plan, amount in plan_totals.items():
            plan_report += f"• <b>{plan}</b>: ₹{amount}\n"

        # ---------- MONTHLY SUMMARY ----------
        monthly_totals = {}

        for p in payments:
            month = p.created_at.strftime("%Y-%m")
            monthly_totals[month] = monthly_totals.get(month, 0) + p.amount

        monthly_report = ""
        for month, amount in monthly_totals.items():
            monthly_report += f"• <b>{month}</b>: ₹{amount}\n"

        # Prepare final admin message
        text = (
            "📊 <b>Admin Revenue Dashboard</b>\n\n"
            f"👥 <b>Active Users:</b> {active_count}\n"
            f"💰 <b>Total Revenue (All Time):</b> ₹{total_revenue}\n\n"
            "📦 <b>Plan-wise Revenue:</b>\n"
            f"{plan_report}\n"
            "🗓 <b>Monthly Revenue Summary:</b>\n"
            f"{monthly_report}"
        )

        await message.answer(text)
