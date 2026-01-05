from aiogram import Router
from aiogram.types import Message
import os

from backend.bot.utils.admin import is_admin
from backend.app.db.session import async_session
from backend.app.db.models import User

router = Router()

CHANNEL_ID = int(os.getenv("TELEGRAM_CHANNEL_ID"))

@router.message(lambda m: m.text.startswith("/remove"))
async def remove_user(message: Message):
    if not is_admin(message.from_user.id):
        return

    try:
        _, user_id = message.text.split()
        user_id = int(user_id)
    except:
        await message.answer("Usage: /remove <user_id>")
        return

    async with async_session() as session:
        user = await session.get(User, user_id)
        if user:
            user.is_active = False
            await session.commit()

    # ✅ USE message.bot (no import, no circular dependency)
    await message.bot.ban_chat_member(CHANNEL_ID, user_id)
    await message.bot.unban_chat_member(CHANNEL_ID, user_id)

    await message.answer(f"❌ User {user_id} removed")
