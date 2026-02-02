from aiogram import Router, F
from aiogram.types import Message
from sqlalchemy import select

from backend.app.db.session import async_session
from backend.app.db.models import Channel
from backend.bot.utils.admin import is_admin

router = Router()


# ======================================================
# /addchannel
# Format:
# /addchannel name | chat_id | description
# ======================================================

@router.message(F.text.startswith("/addchannel"))
async def add_channel(message: Message):
    if not is_admin(message.from_user.id):
        return

    try:
        _, data = message.text.split(" ", 1)
        name, chat_id, description = [x.strip() for x in data.split("|")]
    except Exception:
        await message.answer(
            "Usage:\n"
            "/addchannel Name | -100123456789 | Description"
        )
        return

    async with async_session() as session:
        channel = Channel(
            name=name,
            telegram_chat_id=int(chat_id),
            description=description
        )

        session.add(channel)
        await session.commit()

    await message.answer(f"✅ Channel '{name}' added successfully")


# ======================================================
# /channels_admin → list channels
# ======================================================

@router.message(F.text == "/channels_admin")
async def list_channels(message: Message):
    if not is_admin(message.from_user.id):
        return

    async with async_session() as session:
        result = await session.execute(select(Channel))
        channels = result.scalars().all()

    if not channels:
        await message.answer("No channels added yet.")
        return

    text = "📺 Channels\n\n"

    for ch in channels:
        status = "✅" if ch.is_active else "❌"
        text += f"{status} {ch.name} ({ch.telegram_chat_id})\n"

    await message.answer(text)
