from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command, CommandObject

from sqlalchemy import select

from backend.app.db.session import async_session
from backend.app.db.models import User, Membership


router = Router()


# =====================================================
# /broadcast → ALL USERS
# =====================================================
@router.message(Command("broadcast"))
async def broadcast_all(message: Message, command: CommandObject):

    if not command.args:
        await message.answer("Usage:\n/broadcast your message here")
        return

    text = command.args

    async with async_session() as session:
        result = await session.execute(select(User.telegram_id))
        users = [r[0] for r in result.fetchall()]

    sent = 0

    for tg_id in users:
        try:
            await message.bot.send_message(tg_id, text)
            sent += 1
        except:
            pass

    await message.answer(f"✅ Sent to {sent} users")


# =====================================================
# /broadcast_channel 5 message
# =====================================================
@router.message(Command("broadcast_channel"))
async def broadcast_channel(message: Message, command: CommandObject):

    if not command.args:
        await message.answer(
            "Usage:\n/broadcast_channel <channel_id> message"
        )
        return

    parts = command.args.split(" ", 1)

    if len(parts) < 2:
        await message.answer("Provide channel id + message")
        return

    channel_id = int(parts[0])
    text = parts[1]

    async with async_session() as session:

        result = await session.execute(
            select(User.telegram_id)
            .join(Membership, Membership.user_id == User.id)
            .where(
                Membership.channel_id == channel_id,
                Membership.is_active == True
            )
        )

        users = [r[0] for r in result.fetchall()]

    sent = 0

    for tg_id in users:
        try:
            await message.bot.send_message(tg_id, text)
            sent += 1
        except:
            pass

    await message.answer(f"✅ Sent to {sent} users of channel {channel_id}")
