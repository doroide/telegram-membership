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
    # -----------------------------
    # Read raw body & signature
    # -----------------------------
    body = await request.body()
    received_signature = request.headers.get("X-Razorpay-Signature")

    print("✅ WEBHOOK HIT")

    webhook_secret = os.getenv("RAZORPAY_WEBHOOK_SECRET")
    if not webhook_secret:
        raise HTTPException(status_code=500, detail="Webhook secret missing")

    expected_signature = hmac.new(
        webhook_secret.encode("utf-8"),
        body,
        hashlib.sha256
    ).hexdigest()

    if expected_signature != received_signature:
        raise HTTPException(status_code=400, detail="Invalid Razorpay signature")

    # -----------------------------
    # Parse payload
    # -----------------------------
    payload = json.loads(body)
    event = payload.get("event")
    print("EVENT:", event)

    if event != "payment.captured":
        return {"status": "ignored"}

    # -----------------------------
    # Extract payment & notes
    # (Payment Links safe)
    # -----------------------------
    payment = payload["payload"]["payment"]["entity"]

    notes = payment.get("notes") or payload["payload"].get(
        "payment_link", {}
    ).get("entity", {}).get("notes", {})

    telegram_user_id = notes.get("telegram_user_id")
    plan_id = notes.get("plan_id")

    print("USER:", telegram_user_id)
    print("PLAN:", plan_id)

    if not telegram_user_id or not plan_id:
        raise HTTPException(status_code=400, detail="Missing telegram_user_id or plan_id")

    # -----------------------------
    # Plan & expiry calculation
    # -----------------------------
    plan = PLANS[plan_id]

    start_date = datetime.utcnow()
    expiry_date = start_date + relativedelta(months=plan["months"])

    # -----------------------------
    # SAVE SUBSCRIPTION (STEP 2)
    # -----------------------------
    async with async_session() as session:
        sub = Subscription(
            telegram_user_id=str(telegram_user_id),
            plan_id=plan_id,
            expires_at=expiry_date,
            active=True
        )
        session.add(sub)
        await session.commit()

    # -----------------------------
    # Create invite link
    # -----------------------------
    channel_id = int(os.getenv("TELEGRAM_CHANNEL_ID"))

    invite = await bot.create_chat_invite_link(
        chat_id=channel_id,
        member_limit=1
    )

    # -----------------------------
    # Send invite to user
    # -----------------------------
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
