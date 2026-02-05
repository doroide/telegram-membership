from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command

from datetime import datetime
from sqlalchemy import select

from backend.app.db.session import async_session
from backend.app.db.models import User, Membership, Channel


router = Router()


# =====================================================
# /myplans
# =====================================================
@router.message(Command("myplans"))
async def my_plans_handler(message: Message):
    telegram_id = message.from_user.id

    async with async_session() as session:

        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar()

        if not user:
            await message.answer("❌ No memberships found.")
            return

        result = await session.execute(
            select(Membership, Channel)
            .join(Channel)
            .where(Membership.user_id == user.id)
        )

        rows = result.all()

    if not rows:
        await message.answer("❌ No memberships found.")
        return

    text = "📋 <b>Your Memberships</b>\n\n"

    now = datetime.utcnow()

    for membership, channel in rows:

        expiry = membership.expiry_date
        expiry_str = expiry.strftime("%d %b %Y")

        if expiry > now:
            status = "✅ Active"
        else:
            status = "❌ Expired"

        text += (
            f"<b>{channel.name}</b>\n"
            f"{status}\n"
            f"Expiry: {expiry_str}\n\n"
        )

    await message.answer(text)
