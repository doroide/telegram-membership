from aiogram import Router, F
from aiogram.types import Message
from sqlalchemy import select

from backend.app.db.session import async_session
from backend.app.db.models import User
from backend.bot.utils.admin import is_admin
from backend.bot.bot import bot

router = Router()


@router.message(F.text.startswith("/broadcast"))
async def broadcast(message: Message):

    if not is_admin(message.from_user.id):
        return

    try:
        text = message.text.split(" ", 1)[1]
    except Exception:
        await message.answer("/broadcast your message")
        return

    async with async_session() as session:
        result = await session.execute(select(User.id))
        users = result.scalars().all()

    sent = 0

    for uid in users:
        try:
            await bot.send_message(uid, text)
            sent += 1
        except Exception:
            pass

    await message.answer(f"✅ Sent to {sent} users")
