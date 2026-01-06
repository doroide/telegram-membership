import os
import hmac
import hashlib
from datetime import datetime, timedelta

import httpx
from fastapi import APIRouter, Request, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.session import async_session
from backend.app.db.models import User, Subscription
from backend.app.config.plans import PLANS

router = APIRouter()


# -----------------------------
# Razorpay signature verification
# -----------------------------
def verify_signature(body: bytes, signature: str):
    secret = os.getenv("RAZORPAY_WEBHOOK_SECRET")
    if not secret:
        raise RuntimeError("RAZORPAY_WEBHOOK_SECRET not set")

    expected_signature = hmac.new(
        secret.encode(),
        body,
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected_signature, signature):
        raise HTTPException(status_code=400, detail="Invalid Razorpay signature")


# -----------------------------
# Send Telegram invite link
# -----------------------------
async def send_invite_link(telegram_id: int):
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    channel_id = os.getenv("TELEGRAM_CHANNEL_ID")

    if not bot_token or not channel_id:
        raise RuntimeError("Telegram bot config missing")

    async with httpx.AsyncClient() as client:
        # Create single-use invite link
        invite_resp = await client.post(
            f"https://api.telegram.org/bot{bot_token}/createChatInviteLink",
            json={
                "chat_id": channel_id,
                "member_limit": 1,
            },
        )

        invite_data = invite_resp.json()
        if not invite_data.get("ok"):
            raise RuntimeError(f"Failed to create invite link: {invite_data}")

        invite_link = invite_data["result"]["invite_link"]

        # Send message to user
        await client.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={
                "chat_id": telegram_id,
                "text": (
                    "✅ *Payment Successful!*\n\n"
                    "Here is your private channel access:\n"
                    f"{invite_link}"
                ),
                "parse_mode": "Markdown",
            },
        )


# -----------------------------
# Razorpay webhook endpoint
# -----------------------------
@router.post("/webhook")
async def razorpay_webhook(request: Request):
    raw_body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature")

    if not signature:
        raise HTTPException(status_code=400, detail="Missing Razorpay signature")

    verify_signature(raw_body, signature)

    payload = await request.json()
    event = payload.get("event")

    # Only handle successful payments
    if event != "payment.captured":
        return {"status": "ignored"}

    payment = payload["payload"]["payment"]["entity"]
    notes = payment.get("notes", {})

    telegram_id = int(notes.get("telegram_user_id"))
    plan_id = notes.get("plan_id")

    if not plan_id or plan_id not in PLANS:
        raise HTTPException(status_code=400, detail="Invalid plan_id")

    plan = PLANS[plan_id]
    duration_days = plan["duration_days"]

    expires_at = datetime.utcnow() + timedelta(days=duration_days)

    async with async_session() as session:  # type: AsyncSession
        # Check if user exists
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            user = User(
                id=telegram_id,
                telegram_id=telegram_id,
                plan_id=plan_id,
                status="active",
                start_date=datetime.utcnow(),
                expiry_date=expires_at,
            )
            session.add(user)
        else:
            user.plan_id = plan_id
            user.expiry_date = expires_at
            user.status = "active"

        # Create subscription record
        subscription = Subscription(
            telegram_user_id=telegram_id,
            plan_id=plan_id,
            expires_at=expires_at,
            active=True,
        )
        session.add(subscription)

        await session.commit()

    # Send invite AFTER DB commit
    await send_invite_link(telegram_id)

    return {"status": "success"}
