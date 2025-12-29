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
    body = await request.body()
    received_signature = request.headers.get("X-Razorpay-Signature")

    print("✅ WEBHOOK HIT")

    secret = os.getenv("RAZORPAY_KEY_SECRET")
    if not secret:
        raise HTTPException(status_code=500, detail="Missing Razorpay secret")

    expected_signature = hmac.new(
        secret.encode(),
        body,
        hashlib.sha256
    ).hexdigest()

    if received_signature != expected_signature:
        raise HTTPException(status_code=400, detail="Invalid signature")

    payload = json.loads(body)
    print("EVENT:", payload.get("event"))

    if payload.get("event") != "payment.captured":
        return {"status": "ignored"}

    # ✅ SAFE extraction for Payment Links
    payment_entity = payload["payload"]["payment"]["entity"]

    notes = payment_entity.get("notes", {})
    telegram_user_id = notes.get("telegram_user_id")
    plan_id = notes.get("plan_id")

    print("USER:", telegram_user_id)
    print("PLAN:", plan_id)

    if not telegram_user_id or not plan_id:
        raise HTTPException(status_code=400, detail="Missing notes data")

    plan = PLANS[plan_id]

    start_date = datetime.utcnow()
    expiry_date = start_date + relativedelta(months=plan["months"])

    channel_id = int(os.getenv("TELEGRAM_CHANNEL_ID"))

    invite = await bot.create_chat_invite_link(
        chat_id=channel_id,
        member_limit=1
    )

    await bot.send_message(
        chat_id=int(telegram_user_id),
        text=(
            "🎉 <b>Payment Successful!</b>\n\n"
            f"📦 <b>Plan:</b> {plan['label']}\n"
            f"⏳ <b>Valid till:</b> {expiry_date.date()}\n\n"
            f"🔗 <b>Join the channel:</b>\n{invite.invite_link}"
        )
    )

    print("✅ INVITE SENT")

    return {"status": "ok"}
