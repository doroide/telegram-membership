import os
import hmac
import hashlib
from datetime import datetime, timedelta

from fastapi import APIRouter, Request, HTTPException
from sqlalchemy import select

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

    if payload.get("event") != "payment.captured":
        return {"status": "ignored"}

    payment_entity = payload["payload"]["payment"]["entity"]

    telegram_id = int(payment_entity["notes"]["telegram_user_id"])
    plan_id = payment_entity["notes"]["plan_id"]
    razorpay_payment_id = payment_entity["id"]
    amount = payment_entity["amount"] / 100  # paise → INR

    plan = PLANS.get(plan_id)
    if not plan:
        raise HTTPException(status_code=400, detail="Invalid plan")

    expiry_date = datetime.utcnow() + timedelta(days=plan["days"])

    async with async_session() as session:

        # 🔎 Fetch user by telegram_id (NOT primary key)
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()

        if user:
            user.plan_id = plan_id
            user.expiry_date = expiry_date
            user.status = "active"
            user.reminded_1d = False
            user.reminded_3d = False
        else:
            user = User(
                telegram_id=telegram_id,
                plan_id=plan_id,
                expiry_date=expiry_date,
                status="active",
                reminded_1d=False,
                reminded_3d=False,
            )
            session.add(user)

        # 💳 Save payment
        payment = Payment(
            telegram_id=telegram_id,
            plan_id=plan_id,
            razorpay_payment_id=razorpay_payment_id,
            amount=amount,
            paid_at=datetime.utcnow(),
        )
        session.add(payment)

        await session.commit()

    return {"status": "ok"}
