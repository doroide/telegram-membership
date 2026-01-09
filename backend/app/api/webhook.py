from fastapi import APIRouter, Request
from sqlalchemy import select
from datetime import datetime, timedelta

from backend.app.db.session import async_session
from backend.app.db.models import User

router = APIRouter()

CHANNEL_ID = -1002782697491

PLANS = {
    "plan_199_30d": {"duration_days": 30},
    "plan_499_90d": {"duration_days": 90},
    "plan_799_180d": {"duration_days": 180},
}


@router.post("/webhook")
async def razorpay_webhook(request: Request):
    data = await request.json()
    print("⚡ Razorpay Webhook Hit:", data)

    event = data.get("event")
    payment = data.get("payload", {}).get("payment", {}).get("entity", {})
    notes = payment.get("notes", {})

    telegram_id = notes.get("telegram_id")
    plan_id = notes.get("plan_id")

    if not telegram_id or not plan_id:
        print("❌ Missing Notes:", notes)
        return {"error": "missing parameters"}

    telegram_id = str(telegram_id)

    # Import bot dynamically to avoid circular import
    from backend.bot.bot import bot, get_access_link

    # ==========================================================
    # PAYMENT FAILED
    # ==========================================================
    if event == "payment.failed":
        async with async_session() as session:

            result = await session.execute(select(User).where(User.telegram_id == telegram_id))
            user = result.scalar_one_or_none()

            if not user:
                print("❌ User not found in DB")
                return {"error": "user not found"}

            user.attempts_failed += 1
            await session.commit()

            # Notify and stop execution
            if user.attempts_failed < 3:
                await bot.send_message(
                    telegram_id,
                    f"⚠️ Payment Failed Attempt {user.attempts_failed}/3. Retrying...",
                    parse_mode="Markdown"
                )
                return {"retrying": True}

            # 3rd attempt — remove user
            user.status = "inactive"
            await session.commit()

            try:
                await bot.ban_chat_member(CHANNEL_ID, int(telegram_id))
            except Exception:
                pass

            await bot.send_message(
                telegram_id,
                "❌ Payment Failed 3 Times. You have been removed from the channel.",
                parse_mode="Markdown"
            )

            return {"removed": True}

    # ==========================================================
    # PAYMENT SUCCESS
    # ==========================================================
    if event == "payment.captured":

        duration_days = PLANS[plan_id]["duration_days"]

        async with async_session() as session:

            result = await session.execute(select(User).where(User.telegram_id == telegram_id))
            user = result.scalar_one_or_none()

            # ------------------------------
            # RENEW EXISTING USER
            # ------------------------------
            if user:
                user.status = "active"
                user.attempts_failed = 0

                if user.expiry_date and user.expiry_date > datetime.utcnow():
                    user.expiry_date += timedelta(days=duration_days)
                else:
                    user.expiry_date = datetime.utcnow() + timedelta(days=duration_days)

                await session.commit()

                link = await get_access_link()
                await bot.send_message(
                    telegram_id,
                    f"🎉 *Subscription Renewed!*\nNew expiry: {user.expiry_date.strftime('%d-%m-%Y')}\n"
                    f"👉 Channel Access: {link}",
                    parse_mode="Markdown"
                )

                print("✔ Renewal processed and link sent")
                return {"renewed": True}

            # ------------------------------
            # NEW USER REGISTRATION
            # ------------------------------
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

            link = await get_access_link()

            await bot.send_message(
                telegram_id,
                f"🎉 *Welcome!*\nYour subscription is active.\n"
                f"👉 Join Channel: {link}",
                parse_mode="Markdown"
            )

            print("✔ New user created and link sent")
            return {"created": True}

    return {"ignored": True}
