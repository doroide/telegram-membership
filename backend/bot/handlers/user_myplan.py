from aiogram import Router, F
from aiogram.types import Message
from sqlalchemy import select
from datetime import datetime

from backend.app.db.session import async_session
from backend.app.db.models import Membership, Channel

router = Router()


@router.message(F.text == "/myplan")
async def my_plan(message: Message):

    user_id = message.from_user.id

    async with async_session() as session:

        result = await session.execute(
            select(Membership)
            .where(Membership.user_id == user_id)
            .where(Membership.is_active == True)
        )

        memberships = result.scalars().all()

        if not memberships:
            await message.answer("No active plans.")
            return

        text = "📋 *Your Plans*\n\n"

        for m in memberships:
            channel = await session.get(Channel, m.channel_id)

            if m.expiry_date:
                days_left = (m.expiry_date - datetime.utcnow()).days
                expiry = f"{m.expiry_date.date()} ({days_left} days left)"
            else:
                expiry = "Lifetime"

            text += (
                f"📺 {channel.name}\n"
                f"Plan: {m.plan}\n"
                f"Expiry: {expiry}\n\n"
            )

        await message.answer(text, parse_mode="Markdown")
