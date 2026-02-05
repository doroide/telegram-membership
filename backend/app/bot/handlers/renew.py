from aiogram import Router
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command

from sqlalchemy import select

from backend.app.db.session import async_session
from backend.app.db.models import User, Membership, Channel


router = Router()


# =====================================================
# /renew COMMAND
# =====================================================
@router.message(Command("renew"))
async def renew_handler(message: Message):
    telegram_id = message.from_user.id

    async with async_session() as session:

        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar()

        if not user:
            await message.answer("❌ No membership found. Contact admin.")
            return

        result = await session.execute(
            select(Membership, Channel)
            .join(Channel)
            .where(
                Membership.user_id == user.id,
                Membership.is_active == True
            )
        )

        rows = result.all()

    if not rows:
        await message.answer("❌ No active memberships to renew.")
        return

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=channel.name,
                    callback_data=f"userch_{channel.id}"
                )
            ]
            for membership, channel in rows
        ]
    )

    await message.answer(
        "🔄 Select channel to renew:",
        reply_markup=kb
    )
