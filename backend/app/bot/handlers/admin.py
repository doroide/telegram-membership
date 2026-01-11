from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from sqlalchemy import select
from datetime import datetime, timedelta

# DB imports
from backend.app.db.session import async_session
from backend.app.db.models import User

# Admin Filter
from backend.app.bot.filters.admin_filter import AdminFilter

admin_router = Router()

# PLAN → DAYS Mapping
PLAN_DAYS = {
    "plan_199_1m": 30,
    "plan_399_3m": 90,
    "plan_599_6m": 180,
    "plan_799_12m": 365
}


# ======================
# /add_user (ADMIN ONLY)
# ======================
@admin_router.message(AdminFilter(), Command("add_user"))
async def add_user(message: Message):
    args = message.text.split()

    if len(args) < 3:
        return await message.answer(
            "Usage:\n/add_user <telegram_id> <plan>\n\nExample:\n/add_user 123456789 plan_199_1m"
        )

    telegram_id = args[1].strip()
    plan = args[2].strip()

    if plan not in PLAN_DAYS:
        return await message.answer("❌ Invalid plan. Please use a valid plan name.")

    days = PLAN_DAYS[plan]
    expiry_date = datetime.now() + timedelta(days=days)

    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar()

        if user:
            user.plan = plan
            user.expiry_date = expiry_date
            user.is_active = True
        else:
            user = User(
                telegram_id=telegram_id,
                username=None,
                plan=plan,
                expiry_date=expiry_date,
                is_active=True
            )
            session.add(user)

        await session.commit()

    # Try sending message to user
    try:
        await message.bot.send_message(
            chat_id=telegram_id,
            text=f"🎉 Your subscription has been activated manually!\n\n"
                 f"Plan: {plan}\n"
                 f"Expiry Date: {expiry_date.strftime('%Y-%m-%d')}"
        )
    except:
        pass

    await message.answer(
        f"✅ User added/updated successfully.\n\n"
        f"Telegram ID: {telegram_id}\n"
        f"Plan: {plan}\n"
        f"Expiry: {expiry_date.strftime('%Y-%m-%d')}"
    )
