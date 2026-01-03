import os
from datetime import datetime
from sqlalchemy import select

from backend.bot.bot import bot
from backend.app.db.session import async_session
from backend.app.db.models import Subscription

CHANNEL_ID = int(os.getenv("TELEGRAM_CHANNEL_ID"))


async def run_expiry_check():
    print("⏰ Running expiry check")

    async with async_session() as session:
        result = await session.execute(
            select(Subscription).where(
                Subscription.active == True,
                Subscription.expires_at < datetime.utcnow()
            )
        )

        expired_subs = result.scalars().all()

        for sub in expired_subs:
            try:
                # Remove user from channel
                await bot.ban_chat_member(
                    chat_id=CHANNEL_ID,
                    user_id=int(sub.telegram_user_id)
                )

                # OPTIONAL: notify user
                await bot.send_message(
                    int(sub.telegram_user_id),
                    "⛔ Your subscription has expired. Please renew to rejoin."
                )

                print(f"❌ Removed user {sub.telegram_user_id}")

            except Exception as e:
                print("Failed to remove user:", e)

            # Mark subscription inactive
            sub.active = False

        await session.commit()
