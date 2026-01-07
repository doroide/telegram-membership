from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from datetime import datetime, timedelta

from backend.app.db.session import async_session
from backend.app.db.models import User

router = Router()

ADMIN_ID = 5793624035  # CHANGE TO YOUR TELEGRAM ID


@router.message(Command("retry_failed"))
async def retry_failed(message: Message):
    if message.from_user.id != ADMIN_ID:
        return await message.answer("❌ Not authorized.")

    parts = message.text.split()
    if len(parts) != 2:
        return await message.answer("❗ Usage: /retry_failed <telegram_id>")

    telegram_id = parts[1]

    async with async_session() as session:
        result = await session.execute(
            User.select().where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            return await message.answer("❌ User not found in database.")

        # Reset failure attempts
        user.attempts_failed = 0
        user.status = "active"

        # Add 3 extra days temporarily
        user.expiry_date = datetime.utcnow() + timedelta(days=3)

        await session.commit()

    await message.answer(
        f"✅ Retry triggered for user <b>{telegram_id}</b>\n"
        f"User is temporarily reactivated for 3 days.",
        parse_mode="HTML"
    )
