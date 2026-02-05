import os
import hmac
import hashlib
from datetime import datetime, timedelta

from fastapi import APIRouter, Request, Header, HTTPException
from sqlalchemy import select

from backend.app.db.session import async_session
from backend.app.db.models import User, Membership, Channel
from backend.bot.bot import bot


router = APIRouter()

RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET")


# =====================================================
# SIGNATURE VERIFICATION
# =====================================================
def verify_signature(body: str, signature: str):
    if not RAZORPAY_WEBHOOK_SECRET:
        raise RuntimeError("RAZORPAY_WEBHOOK_SECRET missing")

    generated = hmac.new(
        RAZORPAY_WEBHOOK_SECRET.encode(),
        body.encode(),
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(generated, signature)


# =====================================================
# WEBHOOK
# =====================================================
@router.post("/webhook")
async def razorpay_webhook(
    request: Request,
    x_razorpay_signature: str = Header(None)
):
    body = await request.body()
    body_str = body.decode()

    # 1️⃣ VERIFY SIGNATURE
    if not verify_signature(body_str, x_razorpay_signature):
        raise HTTPException(status_code=400, detail="Invalid signature")

    data = await request.json()

    event = data.get("event")

    # only process successful payments
    if event != "payment.captured":
        return {"status": "ignored"}

    payment = data.get("payload", {}).get("payment", {}).get("entity", {})
    notes = payment.get("notes", {})

    # =================================================
    # READ NOTES (VERY IMPORTANT)
    # =================================================
    try:
        telegram_id = int(notes["telegram_id"])
        channel_id = int(notes["channel_id"])
        validity_days = int(notes["validity_days"])
        amount = int(notes["amount"])
    except:
        return {"error": "invalid notes"}

    expiry_date = datetime.utcnow() + timedelta(days=validity_days)

    try:
        async with async_session() as session:

            # =================================================
            # GET OR CREATE USER
            # =================================================
            result = await session.execute(
                select(User).where(User.telegram_id == telegram_id)
            )
            user = result.scalar()

            if not user:
                user = User(telegram_id=telegram_id)
                session.add(user)
                await session.flush()

            # =================================================
            # CHECK EXISTING MEMBERSHIP
            # =================================================
            result = await session.execute(
                select(Membership).where(
                    Membership.user_id == user.id,
                    Membership.channel_id == channel_id,
                    Membership.is_active == True
                )
            )
            membership = result.scalar()

            # =================================================
            # EXTEND OR CREATE
            # =================================================
            if membership:
                # extend existing
                if membership.expiry_date > datetime.utcnow():
                    membership.expiry_date += timedelta(days=validity_days)
                else:
                    membership.expiry_date = expiry_date

                membership.amount_paid += amount

            else:
                # create new
                membership = Membership(
                    user_id=user.id,
                    channel_id=channel_id,
                    validity_days=validity_days,
                    amount_paid=amount,
                    expiry_date=expiry_date,
                    is_active=True
                )
                session.add(membership)

            await session.commit()

            # =================================================
            # GENERATE INVITE LINK
            # =================================================
            channel = await session.get(Channel, channel_id)

        invite = await bot.create_chat_invite_link(
            chat_id=channel.telegram_chat_id,
            member_limit=1
        )

        expiry_text = membership.expiry_date.strftime("%d-%m-%Y")

        await bot.send_message(
            telegram_id,
            f"✅ Payment Successful!\n\n"
            f"📺 {channel.name}\n"
            f"🗓 Expiry: {expiry_text}\n\n"
            f"👉 Join here:\n{invite.invite_link}"
        )

        return {"status": "success"}

    except Exception as e:
        print("❌ Webhook error:", e)
        raise HTTPException(status_code=500, detail="processing error")
