from datetime import datetime, timedelta
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from backend.app.db.session import async_session
from backend.app.db.models import User
from backend.bot.bot import bot

router = Router()

ADMIN_ID = 5793624035 # CHANGE THIS TO YOUR TELEGRAM USER ID


@router.message(Command("notify_expiring"))
async def notify_expiring(message: Message):

    if message.from_user.id != ADMIN_ID:
        return await message.answer("❌ You are not authorized.")

    now = datetime.utcnow()
    three_days = now + timedelta(days=3)
    one_day = now + timedelta(days=1)

    await message.answer("🔍 Checking for expiring users...")

    async with async_session() as session:
        # Fetch active users only
        result = await session.execute(
            User.select().where(User.status == "active")
        )
        users = result.scalars().all()

    count_3d = 0
    count_1d = 0

    for user in users:
        if not user.expiry_date:
            continue

        # --- 3 DAYS BEFORE EXPIRY ---
        if user.expiry_date.date() == three_days.date() and not user.reminded_3d:
            try:
                await bot.send_message(
                    user.telegram_id,
                    "⏳ *Reminder: Your plan expires in 3 days!*\n"
                    "We will attempt auto-renewal.\n\n"
                    "No action needed.",
                    parse_mode="Markdown"
                )
                user.reminded_3d = True
                count_3d += 1
            except Exception:
                pass

        # --- 1 DAY BEFORE EXPIRY ---
        if user.expiry_date.date() == one_day.date() and not user.reminded_1d:
            try:
                await bot.send_message(
                    user.telegram_id,
                    "⚠️ *Reminder: Your subscription expires tomorrow!*\n"
                    "Auto-renewal will be attempted.",
                    parse_mode="Markdown"
                )
                user.reminded_1d = True
                count_1d += 1
            except Exception:
                pass

    # Save all updates
    async with async_session() as session:
        await session.commit()

    # Admin summary
    await message.answer(
        f"📢 <b>Reminder Summary</b>\n\n"
        f"🔹 3-day reminders sent: <b>{count_3d}</b>\n"
        f"🔹 1-day reminders sent: <b>{count_1d}</b>\n"
        f"✔ Completed.",
        parse_mode="HTML"
    )
