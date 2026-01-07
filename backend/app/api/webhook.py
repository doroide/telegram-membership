from fastapi import APIRouter, Request
from sqlalchemy import select
from datetime import datetime, timedelta

from backend.app.db.session import async_session
from backend.app.db.models import User
from backend.bot.bot import bot, get_access_link

router = APIRouter()

# Telegram Channel ID (replace this!)
CHANNEL_ID = -1002782697491

# Plan Durations (consistent everywhere)
PLANS = {
    "plan_199_30d": {"duration_days": 30},
    "plan_499_90d": {"duration_days": 90},
    "plan_799_180d": {"duration_days": 180},
}


@router.post("/webhook")
async def razorpay_webhook(request: Request):
    data = await request.json()
    event = data.get("event")

    payload = data.get("payload", {})
    payment = payload.get("payment", {}).get("entity", {})
    notes = payment.get("notes", {})

    telegram_id = notes.get("telegram_id")
    plan_id = notes.get("plan_id")

    # Ignore events without required data
    if not telegram_id or not plan_id:
        return {"error": "missing parameters"}

    telegram_id = str(telegram_id)

    # -----------------------------------------
    # 🔴 PAYMENT FAILED
    # -----------------------------------------
    if event == "payment.failed":
        async with async_session() as session:
            result = await session.execute(select(User).where(User.telegram_id == telegram_id))
            user = result.scalar_one_or_none()

            if not user:
                return {"error": "user not found"}

            user.attempts_failed += 1
            await session.commit()

            # Attempt 1 or 2
            if user.attempts_failed < 3:
                await bot.send_message(
                    telegram_id,
                    f"⚠️ *Payment Failed*\nWe will retry again.\nAttempt {user.attempts_failed}/3",
                    parse_mode="Markdown"
                )
                return {"retrying": True}

            # Attempt 3 → Deactivate user
            user.status = "inactive"
            await session.commit()

            # Remove user from channel
            try:
                await bot.ban_chat_member(CHANNEL_ID, int(telegram_id))
            except:
                pass

            # Show plan options
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton("₹199 / 30 days", callback_data="plan_199_30d")],
                    [InlineKeyboardButton("₹499 / 90 days", callback_data="plan_499_90d")],
                    [InlineKeyboardButton("₹799 / 180 days", callback_data="plan_799_180d")],
                ]
            )

            await bot.send_message(
                telegram_id,
                "❌ *Payment Failed 3 Times*\n\n"
                "You have been removed from the channel.\n"
                "Please choose a plan to rejoin:",
                reply_markup=keyboard,
                parse_mode="Markdown"
            )

            return {"status": "deactivated"}

    # -----------------------------------------
    # 🟢 PAYMENT SUCCESS
    # -----------------------------------------
    if event == "payment.captured":
        duration_days = PLANS[plan_id]["duration_days"]

        async with async_session() as session:
            result = await session.execute(select(User).where(User.telegram_id == telegram_id))
            user = result.scalar_one_or_none()

            # ---------------------------
            # Existing user → Renew plan
            # ---------------------------
            if user:
                user.status = "active"
                user.attempts_failed = 0

                if user.expiry_date and user.expiry_date > datetime.utcnow():
                    user.expiry_date += timedelta(days=duration_days)
                else:
                    user.expiry_date = datetime.utcnow() + timedelta(days=duration_days)

                await session.commit()

                await bot.send_message(
                    telegram_id,
                    f"✅ *Payment Received!*\nYour plan has been renewed.\n"
                    f"📅 New Expiry: *{user.expiry_date.strftime('%d-%m-%Y')}*",
                    parse_mode="Markdown"
                )

                return {"renewed": True}

            # ---------------------------
            # New User → Create record
            # ---------------------------
            expiry = datetime.utcnow() + timedelta(days=duration_days)

            new_user = User(
                telegram_id=telegram_id,
                plan_id=plan_id,
                status="active",
                expiry_date=expiry,
                attempts_failed=0,
            )
            session.add(new_user)
            await session.commit()

            # Send join link
            link = await get_access_link()

            await bot.send_message(
                telegram_id,
                f"🎉 *Payment Successful!*\nWelcome aboard!\n\n"
                f"📅 Valid for {duration_days} days\n\n"
                f"👉 Join Channel: {link}",
                parse_mode="Markdown"
            )

            return {"created": True}

    return {"status": "ignored"}
