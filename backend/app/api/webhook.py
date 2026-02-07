import os
import hmac
import hashlib
from datetime import datetime, timedelta

from fastapi import APIRouter, Request, Header, HTTPException
from sqlalchemy import select

from backend.app.db.session import async_session
from backend.app.db.models import User, Membership, Channel, Payment
from backend.bot.bot import bot

router = APIRouter()

RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET")


# =====================================================
# VERIFY SIGNATURE
# =====================================================
def verify_signature(body: bytes, signature: str):
    if not RAZORPAY_WEBHOOK_SECRET:
        print("⚠️ WARNING: RAZORPAY_WEBHOOK_SECRET not set!")
        return False
    
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
    
    print("🔔 Razorpay webhook received")

    if not verify_signature(body, x_razorpay_signature):
        print("❌ Invalid signature")
        raise HTTPException(400, "Invalid signature")

    data = await request.json()
    event = data.get("event")
    
    print(f"📨 Event type: {event}")

    if event != "payment.captured":
        print(f"⏭️ Ignoring event: {event}")
        return {"ignored": True}

    # Get payment entity
    payment_entity = data["payload"]["payment"]["entity"]
    notes = payment_entity.get("notes", {})
    
    print(f"📝 Notes: {notes}")

    try:
        telegram_id = int(notes["telegram_id"])
        channel_id = int(notes["channel_id"])
        validity_days = int(notes["validity_days"])
        amount = float(notes["amount"])
    except (KeyError, ValueError) as e:
        print(f"❌ Missing or invalid notes: {e}")
        raise HTTPException(400, f"Invalid notes: {e}")

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
            user = User(
                telegram_id=telegram_id,
                plan_slab="A"
            )
            session.add(user)
            await session.flush()
            print(f"✅ Created user: {telegram_id}")

        # =========================================
        # GET CHANNEL
        # =========================================
        result = await session.execute(
            select(Channel).where(Channel.id == channel_id)
        )
        channel = result.scalar_one_or_none()
        
        if not channel:
            print(f"❌ Channel {channel_id} not found")
            raise HTTPException(404, "Channel not found")

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
            # Extend existing membership
            membership.expiry_date += timedelta(days=validity_days)
            membership.amount_paid += amount
            print(f"📅 Extended membership until {membership.expiry_date}")
        else:
            # Create new membership
            membership = Membership(
                user_id=user.id,
                channel_id=channel.id,
                start_date=now,
                expiry_date=expiry,
                amount_paid=amount,
                is_active=True
            )
            session.add(membership)
            print(f"✨ Created new membership until {expiry}")

        # =========================================
        # SAVE PAYMENT
        # =========================================
        payment = Payment(
            user_id=user.id,
            channel_id=channel.id,
            amount=amount,
            payment_id=payment_entity.get("id", "unknown"),
            status="captured"
        )

        session.add(payment)
        await session.commit()
        
        print(f"💾 Saved payment: ₹{amount}")

    # =========================================
    # SEND INVITE LINK
    # =========================================
    try:
        invite = await bot.create_chat_invite_link(
            chat_id=channel.telegram_chat_id,
            member_limit=1,
            expire_date=int(expiry.timestamp())
        )
        
        await bot.send_message(
            chat_id=telegram_id,
            text=(
                f"✅ <b>Payment Successful!</b>\n\n"
                f"📺 Channel: <b>{channel.name}</b>\n"
                f"💰 Amount: ₹{amount}\n"
                f"🗓 Valid till: <b>{expiry.strftime('%d %b %Y')}</b>\n\n"
                f"👉 Join here:\n{invite.invite_link}"
            ),
            parse_mode="HTML"
        )
        
        print(f"✅ Sent invite link to {telegram_id}")
        
    except Exception as e:
        print(f"❌ Error sending invite: {e}")
        # Still return success since payment was processed
        await bot.send_message(
            chat_id=telegram_id,
            text=(
                f"✅ Payment received!\n\n"
                f"There was an issue generating your invite link. "
                f"Please contact support with your payment ID."
            )
        )

    return {"ok": True}