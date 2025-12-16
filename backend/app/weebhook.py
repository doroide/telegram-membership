import hmac
import hashlib
from datetime import datetime, timedelta

from fastapi import APIRouter, Request, HTTPException
from aiogram import Bot

from backend.app.config import settings

router = APIRouter()

bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)

@router.post("/razorpay")
async def razorpay_webhook(request: Request):
    body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature")

    expected_signature = hmac.new(
        settings.RAZORPAY_KEY_SECRET.encode(),
        body,
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected_signature, signature):
        raise HTTPException(status_code=400, detail="Invalid signature")

    payload = await request.json()
    event = payload.get("event")

    if event == "payment_link.paid":
        notes = payload["payload"]["payment_link"]["entity"]["notes"]

        telegram_id = int(notes.get("telegram_id"))
        plan = notes.get("plan")

        # 🔹 Create single-use invite link (valid 30 days)
        invite = await bot.create_chat_invite_link(
            chat_id=settings.TELEGRAM_CHANNEL_ID,
            member_limit=1,
            expire_date=datetime.utcnow() + timedelta(days=30)
        )

        # 🔹 Send invite link to user
        await bot.send_message(
            chat_id=telegram_id,
            text=(
                "✅ *Payment successful!*\n\n"
                f"📦 Plan: {plan}\n\n"
                "👉 Click below to join the private channel:\n"
                f"{invite.invite_link}\n\n"
                "⏳ Link valid for 30 days."
            ),
            parse_mode="Markdown"
        )

    return {"status": "ok"}
