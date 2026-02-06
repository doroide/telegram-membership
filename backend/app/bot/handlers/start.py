from aiogram import Router
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from sqlalchemy import select

from backend.app.db.session import async_session
from backend.app.db.models import Channel

router = Router()


# =====================================================
# /start
# =====================================================
@router.message(Command("start"))
async def start_handler(message: Message):

    async with async_session() as session:
        result = await session.execute(
            select(Channel).where(Channel.is_public == True)
        )
        channels = result.scalars().all()

    if not channels:
        await message.answer("⚠️ No channels available right now.")
        return

    keyboard = []

    for ch in channels:
        keyboard.append(
            [InlineKeyboardButton(
                text=ch.name,
                callback_data=f"channel_{ch.id}"
            )]
        )

    markup = InlineKeyboardMarkup(inline_keyboard=keyboard)

    await message.answer(
        "🎬 <b>Available Channels</b>\n\nSelect a channel to view plans 👇",
        reply_markup=markup
    )
