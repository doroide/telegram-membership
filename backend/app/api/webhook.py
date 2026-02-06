import os
import hmac
import hashlib
from datetime import datetime, timedelta

from fastapi import APIRouter, Request, Header, HTTPException
from sqlalchemy import select

from backend.app.db.session import async_session
from backend.app.db.models import User, Membership, Channel, Payment
from backend.bot.bot import bot
from backend.app.config.plans import PLANS


router = APIRouter()

RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET")


# =====================================================
# VERIFY SIGNATURE
# =====================================================
def verify_signature(body: bytes, signature: str):

    generated = hmac.new(
        RAZORPAY_WEBHOOK_SECRET.encode(),
        body,
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

    if not verify_signature(body, x_razorpay_signature):
        raise HTTPException(400, "Invalid signature")

    data = await request.json()

    event = data.get("event")

    if event != "payment.captured":
        return {"ignored": True}

    payment_entity = data["payload"]["payment"]["entity"]
    notes = payment_entity.get("notes", {})

    telegram_id = int(notes["telegram_id"])
    channel_id = int(notes["channel_id"])
    plan_id = notes["plan_id"]

    amount = payment_entity["amount"] / 100  # paise → rupees

    plan = PLANS[plan_id]
    validity_days = plan["duration_days"]

    now = datetime.utcnow()
    expiry = now + timedelta(days=validity_days)

    async with async_session() as session:

        # =========================================
        # GET OR CREATE USER
        # =========================================
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            user = User(telegram_id=telegram_id)
            session.add(user)
            await session.flush()

        # =========================================
        # GET CHANNEL
        # =========================================
        result = await session.execute(
            select(Channel).where(Channel.id == channel_id)
        )
        channel = result.scalar_one()

        # =========================================
        # MEMBERSHIP (extend or create)
        # =========================================
        result = await session.execute(
            select(Membership)
            .where(Membership.user_id == user.id)
            .where(Membership.channel_id == channel.id)
        )

        membership = result.scalar_one_or_none()

        if membership and membership.expiry_date > now:
            membership.expiry_date += timedelta(days=validity_days)
            membership.amount_paid += amount
        else:
            membership = Membership(
                user_id=user.id,
                channel_id=channel.id,
                start_date=now,
                expiry_date=expiry,
                amount_paid=amount,
                is_active=True
            )
            session.add(membership)

        # =========================================
        # SAVE PAYMENT
        # =========================================
        payment = Payment(
            user_id=user.id,
            channel_id=channel.id,
            amount=amount,
            payment_id=payment_entity["id"],
            status="captured"
        )

        session.add(payment)

        await session.commit()

    # =========================================
    # SEND INVITE LINK
    # =========================================
    invite = await bot.create_chat_invite_link(channel.telegram_chat_id)

    await bot.send_message(
        telegram_id,
        f"✅ <b>Payment Successful!</b>\n\n"
        f"📺 Channel: {channel.name}\n"
        f"🗓 Valid till: {membership.expiry_date.strftime('%d %b %Y')}\n\n"
        f"👉 Join here:\n{invite.invite_link}"
    )

    return {"ok": True}
