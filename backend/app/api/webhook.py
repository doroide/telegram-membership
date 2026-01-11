import os
import hmac
import hashlib
from fastapi import APIRouter, Request, Header, HTTPException
from sqlalchemy import select
from datetime import datetime, timedelta

from backend.app.db.session import async_session
from backend.app.db.models import User
from backend.bot.bot import bot, get_access_link

router = APIRouter()

# Razorpay secret for signature verification
RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET")

# Plan durations
PLANS = {
    "plan_199_1m": {"duration_days": 30},
    "plan_399_3m": {"duration_days": 90},
    "plan_599_6m": {"duration_days": 180},
    "plan_799_12m": {"duration_days": 365},
}

CHANNEL_ID = -1002782697491


def verify_signature(body: str, signature: str):
    """Verify Razorpay webhook signature using HMAC SHA256."""
    if not RAZORPAY_WEBHOOK_SECRET:
        raise RuntimeError("RAZORPAY_WEBHOOK_SECRET missing in environment variables")

    generated_signature = hmac.new(
        key=RAZORPAY_WEBHOOK_SECRET.encode(),
        msg=body.encode(),
        digestmod=hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(generated_signature, signature)


@router.post("/webhook")
async def razorpay_webhook(request: Request, 
                           x_razorpay_signature: str = Header(None)):
    body = await request.body()
    payload = request.json()

    # 1. Verify Signature (SECURITY STEP)
    try:
        body_str = body.decode()
        data = await request.json()
        if not verify_signature(body_str, x_razorpay_signature):
            raise HTTPException(status_code=400, detail="Invalid signature")
    except Exception as e:
        print("❌ Signature verification failed:", e)
        raise HTTPException(status_code=400, detail="Invalid signature")

    print("⚡ Valid Razorpay Webhook:", data)

    event = data.get("event")
    payment = data.get("payload", {}).get("payment", {}).get("entity", {})
    notes = payment.get("notes", {})

    plan_id = notes.get("plan_id")
    telegram_id = notes.get("telegram_id")

    if not plan_id or not telegram_id:
        return {"error": "missing notes"}

    if plan_id not in PLANS:
        return {"error": "invalid plan_id"}

    # Only process successful payments
    if event != "payment.captured":
        return {"status": "ignored"}

    duration_days = PLANS[plan_id]["duration_days"]
    telegram_id_str = str(telegram_id)

    # 2. PROCESS USER
    try:
        async with async_session() as session:
            result = await session.execute(
                select(User).where(User.telegram_id == telegram_id_str)
            )
            user = result.scalar_one_or_none()

            # EXISTING USER - RENEW
            if user:
                user.status = "active"

                if user.expiry_date and user.expiry_date > datetime.utcnow():
                    user.expiry_date += timedelta(days=duration_days)
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
                )

                return {"status": "renewed"}

            # NEW USER
            expiry_date = datetime.utcnow() + timedelta(days=duration_days)

            new_user = User(
                telegram_id=telegram_id_str,
                status="active",
                plan_id=plan_id,
                expiry_date=expiry_date,
                attempts_failed=0
            )

            session.add(new_user)
            await session.commit()

            link = await get_access_link()
            expiry_text = expiry_date.strftime("%d-%m-%Y")

            await bot.send_message(
                telegram_id_str,
                f"🎉 <b>Payment Successful!</b>\n"
                f"Welcome to the Premium Channel!\n\n"
                f"🗓 Expiry: <b>{expiry_text}</b>\n"
                f"👉 Access Link: {link}",
            )

            return {"status": "created"}

    except Exception as e:
        print("❌ Webhook processing error:", e)
        raise HTTPException(status_code=500, detail="Internal error")
