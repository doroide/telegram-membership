from datetime import datetime

from sqlalchemy import select

from backend.app.db.session import async_session
from backend.app.db.models import User
from backend.bot.bot import bot
import os

CHANNEL_ID = int(os.getenv("TELEGRAM_CHANNEL_ID"))


async def run_expiry_check():
    now = datetime.utcnow()

    async with async_session() as session:
        result = await session.execute(
            select(User).where(
                User.status == "active",
                User.expiry_date <= now
            )
        )
        expired_users = result.scalars().all()

        for user in expired_users:
            try:
                await bot.ban_chat_member(CHANNEL_ID, user.telegram_id)
                await bot.unban_chat_member(CHANNEL_ID, user.telegram_id)
            except Exception:
                pass  # user may have already left

            user.status = "expired"

        await session.commit()
