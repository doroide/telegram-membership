from fastapi import APIRouter, Request
from sqlalchemy import select
from datetime import datetime, timedelta

from backend.app.db.session import async_session
from backend.app.db.models import User

router = APIRouter()

CHANNEL_ID = -1002782697491

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

    telegram_id_str = str(telegram_id)

    from backend.bot.bot import bot, get_access_link

    if event == "payment.captured":

        if plan_id not in PLANS:
            return {"error": "invalid plan_id"}

        duration_days = PLANS[plan_id]["duration_days"]

        async with async_session() as session:

            result = await session.execute(
                select(User).where(User.telegram_id == telegram_id_str)
            )
            user = result.scalar_one_or_none()

            # EXISTING USER
            if user:

                user.status = "active"
                user.attempts_failed = 0

                if user.expiry_date and user.expiry_date > datetime.utcnow():
                    user.expiry_date = user.expiry_date + timedelta(days=duration_days)
                else:
                    user.expiry_date = datetime.utcnow() + timedelta(days=duration_days)

                await session.commit()

                link = await get_access_link()
                expiry_text = user.expiry_date.strftime("%d-%m-%Y")

                await bot.send_message(
                    telegram_id_str,
                    f"✅ <b>Plan Renewed Successfully!</b>\n"
                    f"🗓 Expiry Date: <b>{expiry_text}</b>\n\n"
                    f"👉 Your Channel Access Link:\n{link}",
                    parse_mode="HTML"
                )

                return {"status": "renewed"}

            # NEW USER
            expiry = datetime.utcnow() + timedelta(days=duration_days)

            new_user = User(
                telegram_id=telegram_id_str,
                plan_id=plan_id,
                status="active",
                expiry_date=expiry,
                attempts_failed=0
            )

            session.add(new_user)
            await session.commit()

            link = await get_access_link()
            expiry_text = expiry.strftime("%d-%m-%Y")

            await bot.send_message(
                telegram_id_str,
                f"🎉 <b>Payment Successful!</b>\n"
                f"Welcome to the Premium Channel!\n\n"
                f"🗓 Your Plan Expiry: <b>{expiry_text}</b>\n\n"
                f"👉 Click to Join: {link}",
                parse_mode="HTML"
            )

            return {"status": "created"}

    return {"status": "ignored"}
