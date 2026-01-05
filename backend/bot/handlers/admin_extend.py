from datetime import timedelta
from aiogram import Router
from aiogram.types import Message

from backend.bot.utils.admin import is_admin
from backend.app.db.session import async_session
from backend.app.db.models import User

router = Router()

@router.message(lambda m: m.text.startswith("/extend"))
async def extend_user(message: Message):
    if not is_admin(message.from_user.id):
        return

    try:
        _, user_id, days = message.text.split()
        user_id = int(user_id)
        days = int(days)
    except:
        await message.answer("Usage: /extend <user_id> <days>")
        return

    async with async_session() as session:
        user = await session.get(User, user_id)
        if not user:
            await message.answer("User not found")
            return

        user.expires_at += timedelta(days=days)
        user.is_active = True
        await session.commit()

    await message.answer(f"✅ Extended user {user_id} by {days} days")
