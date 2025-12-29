from fastapi import APIRouter, Request
import os
import hmac
import hashlib
import json

router = APIRouter()

@router.post("/webhook")
async def razorpay_webhook(request: Request):
    body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature")

    secret = os.getenv("RAZORPAY_KEY_SECRET").encode()
    expected_signature = hmac.new(secret, body, hashlib.sha256).hexdigest()

    if signature != expected_signature:
        return {"status": "invalid signature"}

    payload = json.loads(body)

    payment = payload["payload"]["payment"]["entity"]
    user_id = payment["notes"]["telegram_user_id"]
    plan_id = payment["notes"]["plan_id"]

    # NEXT STEP: add to channel + save subscription

    return {"status": "ok"}
