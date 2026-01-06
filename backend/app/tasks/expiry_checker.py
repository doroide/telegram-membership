import os
import httpx
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.session import async_session
from backend.app.db.models import Subscription, User
from backend.app.config.plans import PLANS


BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID")


async def remove_user_from_channel(telegram_id: int):
    async with httpx.AsyncClient() as client:
        await client.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/banChatMember",
            json={
                "chat_id": CHANNEL_ID,
                "user_id": telegram_id,
            },
        )

        # Allow rejoin after payment
        await client.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/unbanChatMember",
            json={
                "chat_id": CHANNEL_ID,
                "user_id": telegram_id,
            },
        )


def build_plans_keyboard():
    keyboard = []
    for plan_id, plan in PLANS.items():
        keyboard.append([
            {
                "text": plan["label"],
                "callback_data": plan_id
            }
        ])

    return {"inline_keyboard": keyboard}


async def send_expiry_message(telegram_id: int):
    async with httpx.AsyncClient() as client:
        await client.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={
                "chat_id": telegram_id,
                "text": (
                    "❌ *Subscription Expired*\n\n"
                    "You have been removed from the channel because your plan expired.\n\n"
                    "👉 Choose a plan below to rejoin instantly:"
                ),
                "parse_mode": "Markdown",
                "reply_markup": build_plans_keyboard(),
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

            try:
                # 1️⃣ Remove from channel
                await remove_user_from_channel(telegram_id)

                # 2️⃣ Notify user with plans
                await send_expiry_message(telegram_id)

            except Exception as e:
                print(f"❌ Error handling expiry for {telegram_id}: {e}")

            # 3️⃣ Mark subscription inactive
            sub.active = False

            # 4️⃣ Update user status
            await session.execute(
                update(User)
                .where(User.telegram_id == telegram_id)
                .values(status="expired")
            )

        await session.commit()
        print(f"✅ Expiry check complete. Processed {len(expired_subs)} users.")
