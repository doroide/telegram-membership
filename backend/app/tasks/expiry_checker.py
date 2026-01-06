import os
import httpx
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.session import async_session
from backend.app.db.models import Subscription, User


BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID")


async def remove_user_from_channel(telegram_id: int):
    if not BOT_TOKEN or not CHANNEL_ID:
        raise RuntimeError("Telegram config missing")

    async with httpx.AsyncClient() as client:
        await client.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/banChatMember",
            json={
                "chat_id": CHANNEL_ID,
                "user_id": telegram_id,
            },
        )

        # OPTIONAL: unban so user can rejoin if they pay again
        await client.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/unbanChatMember",
            json={
                "chat_id": CHANNEL_ID,
                "user_id": telegram_id,
            },
        )


async def run_expiry_check():
    now = datetime.utcnow()

    async with async_session() as session:  # type: AsyncSession
        result = await session.execute(
            select(Subscription)
            .where(Subscription.active == True)
            .where(Subscription.expires_at <= now)
        )

        expired_subs = result.scalars().all()

        if not expired_subs:
            return

        for sub in expired_subs:
            telegram_id = sub.telegram_user_id

            # 1️⃣ Remove user from channel
            try:
                await remove_user_from_channel(telegram_id)
            except Exception as e:
                print(f"❌ Failed to remove {telegram_id}: {e}")

            # 2️⃣ Mark subscription inactive
            sub.active = False

            # 3️⃣ Update user status
            await session.execute(
                update(User)
                .where(User.telegram_id == telegram_id)
                .values(status="expired")
            )

        await session.commit()
        print(f"✅ Expiry check complete. Removed {len(expired_subs)} users.")
