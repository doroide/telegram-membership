from fastapi import APIRouter, Request, HTTPException
import os
import hmac
import hashlib
import json

router = APIRouter()

@router.post("/webhook")
async def razorpay_webhook(request: Request):
    body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature")

    if not signature:
        raise HTTPException(status_code=400, detail="Missing signature")

    secret = os.getenv("RAZORPAY_KEY_SECRET")
    if not secret:
        raise HTTPException(status_code=500, detail="Webhook secret missing")

    expected_signature = hmac.new(
        secret.encode(),
        body,
        hashlib.sha256
    ).hexdigest()

    if signature != expected_signature:
        raise HTTPException(status_code=400, detail="Invalid signature")

    payload = json.loads(body)

    event = payload.get("event")
    if event != "payment.captured":
        return {"status": "ignored"}

    payment = payload["payload"]["payment"]["entity"]

    telegram_user_id = payment["notes"].get("telegram_user_id")
    plan_id = payment["notes"].get("plan_id")

    print("✅ Payment Captured")
    print("User ID:", telegram_user_id)
    print("Plan ID:", plan_id)
    print("Payment ID:", payment["id"])

    return {"status": "ok"}
