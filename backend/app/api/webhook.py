import os
import json
import hmac
import hashlib
from datetime import datetime

from fastapi import APIRouter, Request, HTTPException
from dateutil.relativedelta import relativedelta

from backend.bot.bot import bot
from backend.app.config.plans import PLANS
from backend.app.db.session import async_session
from backend.app.db.models import Subscription


router = APIRouter()


@router.post("/webhook")
async def razorpay_webhook(request: Request):
    body = await request.body()
    received_signature = request.headers.get("X-Razorpay-Signature")

    print("✅ WEBHOOK HIT")

    webhook_secret = os.getenv("RAZORPAY_WEBHOOK_SECRET")
    if not webhook_secret:
        raise HTTPException(status_code=500, detail="Webhook secret missing")

    expected_signature = hmac.new(
        webhook_secret.encode(),
        body,
        hashlib.sha256
    ).hexdigest()

    if expected_signature != received_signature:
        raise HTTPException(status_code=400, detail="Invalid Razorpay signature")

    payload = json.loads(body)
    event = payload.get("event")
    print("EVENT:", event)

    if event != "payment.captured":
        return {"status": "ignored"}

    payment = payload["payload"]["payment"]["entity"]

    # ✅ IMPORTANT: Payment Links store notes here
    notes = {}

    if "notes" in payment and payment["notes"]:
        notes = payment["notes"]
    else:
        notes = payload["payload"].get("payment_link", {}).get("entity", {}).get("notes", {})

    telegram_user_id = notes.get("telegram_user_id")
    plan_id = notes.get("plan_id")

    print("USER:", telegram_user_id)
    print("PLAN:", plan_id)

    if not telegram_user_id or not plan_id:
        raise HTTPException(status_code=400, detail="Missing telegram_user_id or plan_id")

    plan = PLANS[plan_id]

    start_date = datetime.utcnow()
    expiry_date = start_date + relativedelta(months=plan["months"])

# ===============================
# STEP 2: Save subscription in DB
# ===============================
async with async_session() as session:
    sub = Subscription(
        telegram_user_id=str(telegram_user_id),
        plan_id=plan_id,
        expires_at=expiry_date,
        active=True
    )
    session.add(sub)
    await session.commit()


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
            f"🔗 <b>Join channel:</b>\n{invite.invite_link}"
        )
    )

    print("✅ INVITE SENT")

    return {"status": "ok"}
