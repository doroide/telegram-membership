import asyncio
from datetime import datetime, timedelta

from sqlalchemy import select
from backend.app.db.session import async_session
from backend.app.db.models import User
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# USE REAL CHANNEL ID
CHANNEL_ID = -1002782697491  # <-- replace with your real channel ID


# Correct Aiogram 3.x button format
PLANS_KEYBOARD = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="₹199 / 30 days", callback_data="plan_199_30d")],
        [InlineKeyboardButton(text="₹499 / 90 days", callback_data="plan_499_90d")],
        [InlineKeyboardButton(text="₹799 / 180 days", callback_data="plan_799_180d")],
    ]
)


async def run_expiry_check():
    # Import bot inside function to avoid circular import
    from backend.bot.bot import bot

    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.status == "active")
        )
        users = result.scalars().all()

        now = datetime.utcnow()

        for user in users:
            user_id = int(user.telegram_id)

            # ------------------------------
            # 3 DAYS REMINDER
            # ------------------------------
            if user.expiry_date and not user.reminded_3d:
                if user.expiry_date - timedelta(days=3) <= now < user.expiry_date:
                    try:
                        await bot.send_message(
                            user_id,
                            "⏳ *Your subscription expires in 3 days!*",
                            parse_mode="Markdown"
                        )
                        user.reminded_3d = True
                    except Exception:
                        pass

            # ------------------------------
            # 1 DAY REMINDER
            # ------------------------------
            if user.expiry_date and not user.reminded_1d:
                if user.expiry_date - timedelta(days=1) <= now < user.expiry_date:
                    try:
                        await bot.send_message(
                            user_id,
                            "⚠️ *Your subscription expires in 1 day!*",
                            parse_mode="Markdown"
                        )
                        user.reminded_1d = True
                    except Exception:
                        pass

            # ------------------------------
            # EXPIRY CHECK
            # ------------------------------
            if user.expiry_date and now >= user.expiry_date:
                user.status = "inactive"

                try:
                    await bot.ban_chat_member(CHANNEL_ID, user_id)
                except Exception:
                    pass

                try:
                    await bot.send_message(
                        user_id,
                        "❌ *Your subscription has expired!*\n\n"
                        "You have been removed from the channel.\n"
                        "To rejoin, choose a plan below:",
                        reply_markup=PLANS_KEYBOARD,
                        parse_mode="Markdown"
                    )
                except Exception:
                    pass

            # ------------------------------
            # FAILED AUTO-RENEW ATTEMPTS
            # ------------------------------
            if 1 <= user.attempts_failed < 3:
                try:
                    await bot.send_message(
                        user_id,
                        f"⚠️ Auto-renew attempt failed ({user.attempts_failed}/3). Retrying...",
                        parse_mode="Markdown"
                    )
                except Exception:
                    pass

            # ------------------------------
            # AUTO-REMOVE AFTER 3 FAILURES
            # ------------------------------
            if user.attempts_failed >= 3:
                user.status = "inactive"

                try:
                    await bot.ban_chat_member(CHANNEL_ID, user_id)
                except Exception:
                    pass

                try:
                    await bot.send_message(
                        user_id,
                        "❌ *Auto-renew failed 3 times!*\n"
                        "You have been removed.\nPlease choose a plan:",
                        reply_markup=PLANS_KEYBOARD,
                        parse_mode="Markdown"
                    )
                except Exception:
                    pass

            # Commit individual updates
            await session.commit()
