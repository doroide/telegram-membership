from fastapi import APIRouter, Request
from sqlalchemy import select
from datetime import datetime, timedelta

from backend.app.db.session import async_session
from backend.app.db.models import User

router = APIRouter()

CHANNEL_ID = -1002782697491

# Correct Plan Durations
PLANS = {
    "plan_199_1m": {"duration_days": 30},
    "plan_399_3m": {"duration_days": 90},
    "plan_599_6m": {"duration_days": 180},
    "plan_799_12m": {"duration_days": 365},
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

    # Import here to avoid circular import
    from backend.bot.bot import bot, get_access_link

    # ==========================================================
    # PAYMENT FAILED
    # ==========================================================
    if event == "payment.failed":
        async with async_session() as session:
            result = await session.execute(
                select(User).where(User.telegram_id == telegram_id)
            )
            user = result.scalar_one_or_none()

            if not user:
                return {"error": "user not found"}

            user.attempts_failed += 1
            await session.commit()

            if user.attempts_failed < 3:
                await bot.send_message(
                    telegram_id,
                    f"⚠️ Payment Failed (Attempt {user.attempts_failed}/3). Retrying...",
                    parse_mode="Markdown"
                )
                return {"retrying": True}

            # 3 failed attempts -> deactivate
            user.status = "inactive"
            await session.commit()

            try:
                await bot.ban_chat_member(CHANNEL_ID, int(telegram_id))
            except Exception:
                pass

            await bot.send_message(
                telegram_id,
                "❌ Payment Failed 3 Times. You have been removed.",
                parse_mode="Markdown"
            )

            return {"removed": True}

    # ==========================================================
    # PAYMENT SUCCESS
    # ==========================================================
    if event == "payment.captured":

        duration_days = PLANS[plan_id]["duration_days"]

        async with async_session() as session:

            result = await session.execute(
                select(User).where(User.telegram_id == telegram_id)
            )
            user = result.scalar_one_or_none()

            # ------------------------------
            # RENEW EXISTING USER
            # ------------------------------
            if user:
                user.status = "active"
                user.attempts_failed = 0

                # Correct expiry handling
                if user.expiry_date and user.expiry_date > datetime.utcnow():
                    user.expiry_date = user.expiry_date + timedelta(days=duration_days)
                else:
                    user.expiry_date = datetime.utcnow() + timedelta(days=duration_days)

                await session.commit()

                link = await get_access_link()
                await bot.send_message(
                    telegram_id,
                    f"✅ <b>Plan Renewed!</b>\n"
                    f"New Expiry: <b>{user.expiry_date.strftime('%d-%m-%Y')}</b>\n\n"
                    f"👉 Access Channel: {link}",
                    parse_mode="HTML"
                )

                print("✔ Renewal processed")
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

            print("✔ New user created")
            return {"created": True}

    return {"ignored": True}
