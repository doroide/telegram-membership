from fastapi import APIRouter, Request
from sqlalchemy import select
from datetime import datetime, timedelta

from backend.app.db.session import async_session
from backend.app.db.models import User

router = APIRouter()

CHANNEL_ID = -1002782697491

# VALID PLANS WITH CORRECT DURATIONS
PLANS = {
    "plan_199_1m": {"duration_days": 30},
    "plan_399_3m": {"duration_days": 90},
    "plan_599_6m": {"duration_days": 180},
    "plan_799_12m": {"duration_days": 365},
}


@router.post("/webhook")
async def razorpay_webhook(request: Request):
    data = await request.json()
    print("⚡ Razorpay Webhook Hit:", data
