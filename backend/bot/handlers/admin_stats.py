from aiogram import Router
from aiogram.types import Message
from sqlalchemy import select, func

from backend.bot.utils.admin import is_admin
from backend.app.db.session import async_session
from backend.app.db.models import User

router = Router()

@router.message(lambda msg: msg.text == "/stats")
async def stats_handler(message: Message):
    if not is_admin(message.from_user.id):
        return

    async with async_session() as session:
        total = await session.scalar(select(func.count()).select_from(User))
        active = await session.scalar(
            select(func.count()).where(User.is_active == True)
        )
        expired = total - active

    await message.answer(
        f"📊 *Stats*\n\n"
        f"👥 Total users: {total}\n"
        f"✅ Active: {active}\n"
        f"❌ Expired: {expired}",
        parse_mode="Markdown"
    )
