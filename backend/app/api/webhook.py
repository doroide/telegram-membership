from fastapi import APIRouter, Request
from sqlalchemy import select
from datetime import datetime, timedelta

from backend.app.db.session import async_session
from backend.app.db.models import User

router = APIRouter()

CHANNEL_ID = -1002782697491

# MUST MATCH Razorpay plan_id EXACTLY
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

    plan_id = notes.get("plan_id")
    telegram_id = notes.get("telegram_id")

    if not plan_id or not telegram_id:
        return {"error": "missing notes"}

    # Convert telegram_id to int for DB compatibility 
    try:
        telegram_id = int(telegram_id)
    except:
        print("❌ Invalid telegram_id received:", telegram_id)
        return {"error": "invalid telegram_id"}

    # Import bot dynamically
    from backend.bot.bot import bot, get_access_link

    # =======================
    # PAYMENT SUCCESS
    # =======================
    if event == "payment.captured":

        if plan_id not in PLANS:
            print("❌ Unknown plan returned by Razorpay:", plan_id)
            return {"error": "invalid plan_id"}

        duration_days = PLANS[plan_id]["duration_days"]

        async with async_session() as session:

            result = await session.execute(select(User).where(User.telegram_id == telegram_id))
            user = result.scalar_one_or_none()

            # ------------------------------
            # EXISTING USER RENEWAL
            # ------------------------------
            if user:

                user.status = "active"
                user.attempts_failed = 0

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

                return {"status": "renewed"}

            # ------------------------------
            # NEW USER CREATION
            # ------------------------------
            new_user = User(
                telegram_id=telegram_id,
                plan_id=plan_id,
                status="active",
                expiry_date=datetime.utcnow() + timedelta(days=duration_days),
                attempts_failed=0
            )

            session.add(new_user)
            await session.commit()

            link = await get_access_link()

            await bot.send_message(
                telegram_id,
                f"🎉 <b>Payment Successful!</b>\n"
                f"Welcome to the channel.\n\n"
                f"👉 Join Here: {link}",
                parse_mode="HTML"
            )

            return {"status": "created"}

    return {"status": "ignored"}
