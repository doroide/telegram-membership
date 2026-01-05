import os
import hmac
import hashlib
from datetime import datetime, timedelta

from fastapi import APIRouter, Request, HTTPException

from backend.app.db.session import async_session
from backend.app.db.models import User, Payment
from backend.app.config.plans import PLANS

router = APIRouter()

RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET")


def verify_signature(body: bytes, signature: str):
    expected = hmac.new(
        RAZORPAY_WEBHOOK_SECRET.encode(),
        body,
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=400, detail="Invalid signature")


@router.post("/webhook")
async def razorpay_webhook(request: Request):
    body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature")

    if not signature:
        raise HTTPException(status_code=400, detail="Missing signature")

    verify_signature(body, signature)

    payload = await request.json()

    event = payload.get("event")
    if event != "payment.captured":
        return {"status": "ignored"}

    payment = payload["payload"]["payment"]["entity"]

    telegram_user_id = str(payment["notes"]["telegram_user_id"])
    plan_id = payment["notes"]["plan_id"]
    razorpay_payment_id = payment["id"]
    amount = payment["amount"] / 100  # paise → INR

    plan = PLANS.get(plan_id)
    if not plan:
        raise HTTPException(status_code=400, detail="Invalid plan")

    duration_days = plan["days"]
    expires_at = datetime.utcnow() + timedelta(days=duration_days)

    async with async_session() as session:
        # 1️⃣ Create or update USER (subscription lives here)
        user = await session.get(User, telegram_user_id)

        if user:
            user.plan_id = plan_id
            user.expires_at = expires_at
            user.is_active = True
            user.reminded_1d = False
            user.reminded_3d = False
        else:
            user = User(
                telegram_user_id=telegram_user_id,
                plan_id=plan_id,
                expires_at=expires_at,
                is_active=True,
                reminded_1d=False,
                reminded_3d=False
            )
            session.add(user)

        # 2️⃣ Record PAYMENT
        payment_record = Payment(
            telegram_user_id=telegram_user_id,
            plan_id=plan_id,
            razorpay_payment_id=razorpay_payment_id,
            amount=amount,
            paid_at=datetime.utcnow()
        )
        session.add(payment_record)

        await session.commit()

    return {"status": "ok"}
