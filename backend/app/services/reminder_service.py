import asyncio
from datetime import datetime, timezone
from sqlalchemy import select
from backend.app.db.session import async_session
from backend.app.db.models import User
from aiogram import Bot
import os

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
bot = Bot(token=BOT_TOKEN)

async def reminder_loop():
    while True:
        try:
            async with async_session() as session:
                result = await session.execute(
                    select(User).where(User.is_active == True)
                )
                users = result.scalars().all()

                now = datetime.now(timezone.utc)

                for user in users:
                    if not user.expires_at:
                        continue

                    days_left = (user.expires_at - now).days

                    if days_left == 3 and not user.reminded_3d:
                        await bot.send_message(
                            user.telegram_user_id,
                            "⏰ Your subscription expires in *3 days*.\nRenew to avoid removal.",
                            parse_mode="Markdown"
                        )
                        user.reminded_3d = True

                    elif days_left == 1 and not user.reminded_1d:
                        await bot.send_message(
                            user.telegram_user_id,
                            "⚠️ Your subscription expires *tomorrow*.\nRenew now to continue access.",
                            parse_mode="Markdown"
                        )
                        user.reminded_1d = True

                await session.commit()

        except Exception as e:
            print("Reminder task error:", e)

        await asyncio.sleep(3600)  # run every 1 hour
