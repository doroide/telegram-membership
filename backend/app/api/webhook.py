import os
import hmac
import hashlib
from datetime import datetime, timedelta

from fastapi import APIRouter, Request, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.session import async_session
from backend.app.db.models import User, Subscription
from backend.app.config.plans import PLANS

router = APIRouter()


def verify_signature(body: bytes, signature: str):
    secret = os.getenv("RAZORPAY_WEBHOOK_SECRET")
    if not secret:
        raise RuntimeError("RAZORPAY_WEBHOOK_SECRET not set")

    generated = hmac.new(
        secret.encode(),
        body,
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(generated, signature):
        raise HTTPException(status_code=400, detail="Invalid signature")


@router.post("/webhook")
async def razorpay_webhook(request: Request):
    raw_body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature")

    if not signature:
        raise HTTPException(status_code=400, detail="Missing signature")

    verify_signature(raw_body, signature)

    payload = await request.json()
    event = payload.get("event")

    if event != "payment.captured":
        return {"status": "ignored"}

    payment = payload["payload"]["payment"]["entity"]
    notes = payment.get("notes", {})

    telegram_id = int(notes.get("telegram_user_id"))
    plan_id = notes.get("plan_id")

    if plan_id not in PLANS:
        raise HTTPException(status_code=400, detail="Invalid plan")

    plan = PLANS[plan_id]
    duration_days = plan["duration_days"]

    expires_at = datetime.utcnow() + timedelta(days=duration_days)

    async with async_session() as session:  # type: AsyncSession
        # 🔍 Check if user exists
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

        subscription = Subscription(
            telegram_user_id=telegram_id,
            plan_id=plan_id,
            expires_at=expires_at,
            active=True,
        )
        session.add(subscription)

        await session.commit()

    return {"status": "success"}
