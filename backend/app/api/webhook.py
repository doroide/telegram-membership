import os
import json
import hmac
import hashlib
from datetime import datetime

from fastapi import APIRouter, Request, HTTPException
from dateutil.relativedelta import relativedelta

from backend.bot.bot import bot
from backend.app.config.plans import PLANS

router = APIRouter()


@router.post("/webhook")
async def razorpay_webhook(request: Request):
    # Read raw body for signature verification
    body = await request.body()
    received_signature = request.headers.get("X-Razorpay-Signature")

    if not received_signature:
        raise HTTPException(status_code=400, detail="Missing Razorpay signature")

    secret = os.getenv("RAZORPAY_KEY_SECRET")
    if not secret:
        raise HTTPException(status_code=500, detail="Razorpay secret missing")

    # Verify signature
    expected_signature = hmac.new(
        secret.encode(),
        body,
        hashlib.sha256
    ).hexdigest()

    if expected_signature != received_signature:
        raise HTTPException(status_code=400, detail="Invalid Razorpay signature")

    payload = json.loads(body)

    # We only care about successful payments
    if payload.get("event") != "payment.captured":
        return {"status": "ignored"}

    payment = payload["payload"]["payment"]["entity"]

    telegram_user_id = int(payment["notes"]["telegram_user_id"])
    plan_id = payment["notes"]["plan_id"]

    if plan_id not in PLANS:
        raise HTTPException(status_code=400, detail="Invalid plan ID")

    plan = PLANS[plan_id]

    # Calculate expiry
    start_date = datetime.utcnow()
    expiry_date = start_date + relativedelta(months=plan["months"])

    channel_id = int(os.getenv("TELEGRAM_CHANNEL_ID"))

    # Create single-use invite link
    invite = await bot.create_chat_invite_link(
        chat_id=channel_id,
        member_limit=1
    )

    # Send invite to user
    await bot.send_message(
        chat_id=telegram_user_id,
        text=(
            "🎉 <b>Payment Successful!</b>\n\n"
            f"📦 <b>Plan:</b> {plan['label']}\n"
            f"⏳ <b>Valid till:</b> {expiry_date.date()}\n\n"
            f"🔗 <b>Join the channel:</b>\n"
            f"{invite.invite_link}\n\n"
            "⚠️ This invite is single-use. Do not share it."
        )
    )

    return {"status": "ok"}
