from fastapi import APIRouter, Request, HTTPException
from sqlalchemy import select, and_
from datetime import datetime, timedelta, timezone
from backend.app.db.session import async_session
from backend.app.db.models import User, Channel, Membership, Payment
from backend.bot.bot import bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import hmac
import hashlib
import os
import asyncio
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET")
ADMIN_USERNAME = "Doroide47"


# ======================================================
# SIGNATURE VERIFICATION
# ======================================================

def verify_webhook_signature(payload: bytes, signature: str) -> bool:
    expected_signature = hmac.new(
        RAZORPAY_WEBHOOK_SECRET.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected_signature, signature)


# ======================================================
# RENEWAL HANDLER WITH GRACE PERIOD & DUPLICATE PREVENTION
# ======================================================

async def handle_renewal_payment(db, payment_data, notes):
    """
    Smart renewal handler:
    - Checks grace period (48 hours)
    - Extends existing vs creates new
    - Prevents duplicate active memberships (GOLDEN RULE)
    """
    telegram_id = int(notes.get("telegram_id"))
    channel_id = int(notes.get("channel_id"))
    validity_days = int(notes.get("validity_days"))
    tier = int(notes.get("tier"))
    amount = float(payment_data.get("amount", 0)) / 100
    is_renewal = notes.get("is_renewal") == "true"
    old_membership_id = int(notes.get("old_membership_id", 0))
    
    # Get user
    result = await db.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    
    if not user:
        logger.error(f"User not found: {telegram_id}")
        return False
    
    now = datetime.now(timezone.utc)
    
    # RENEWAL FLOW - Check grace period
    if is_renewal and old_membership_id:
        old_membership = await db.get(Membership, old_membership_id)
        
        if old_membership:
            grace_period_end = old_membership.expiry_date + timedelta(hours=48)
            within_grace = old_membership.expiry_date < now <= grace_period_end
            
            if old_membership.is_active or within_grace:
                # EXTEND existing membership (active or within grace)
                old_membership.expiry_date = old_membership.expiry_date + timedelta(days=validity_days)
                old_membership.is_active = True
                old_membership.amount_paid += amount
                old_membership.reminded_7d = False
                old_membership.reminded_1d = False
                old_membership.reminded_expired = False
                
                logger.info(f"Extended membership {old_membership_id} by {validity_days} days (grace={within_grace})")
                await db.commit()
                return True
            else:
                # Beyond grace - deactivate old
                old_membership.is_active = False
                logger.info(f"Deactivated old membership {old_membership_id} (expired beyond grace)")
    
    # GOLDEN SAFETY RULE: Check for existing active membership
    result = await db.execute(
        select(Membership).where(
            and_(
                Membership.user_id == user.id,
                Membership.channel_id == channel_id,
                Membership.is_active == True
            )
        )
    )
    existing = result.scalar_one_or_none()
    
    if existing:
        # EXTEND existing active membership instead of creating duplicate
        existing.expiry_date = existing.expiry_date + timedelta(days=validity_days)
        existing.amount_paid += amount
        existing.reminded_7d = False
        existing.reminded_1d = False
        
        logger.info(f"Extended existing active membership {existing.id} - NO DUPLICATE CREATED")
        await db.commit()
        return True
    else:
        # CREATE new membership (no active membership exists)
        new_membership = Membership(
            user_id=user.id,
            channel_id=channel_id,
            validity_days=validity_days,
            amount_paid=amount,
            start_date=now,
            expiry_date=now + timedelta(days=validity_days),
            is_active=True,
            tier=tier
        )
        db.add(new_membership)
        
        logger.info(f"Created new membership for user {user.id}, channel {channel_id}")
        await db.commit()
        return True


# ======================================================
# MAIN WEBHOOK ENDPOINT
# ======================================================

@router.post("/webhook")
async def razorpay_webhook(request: Request):
    try:
        payload = await request.body()
        signature = request.headers.get("X-Razorpay-Signature")

        if not verify_webhook_signature(payload, signature):
            raise HTTPException(status_code=400, detail="Invalid signature")

        data = await request.json()
        event = data.get("event")

        logger.info(f"Razorpay webhook event: {event}")

        if event == "payment.captured":
            await handle_payment_captured(data)
        elif event == "subscription.authenticated":
            await handle_subscription_authenticated(data)
        elif event == "subscription.charged":
            await handle_subscription_charged(data)
        elif event == "subscription.halted":
            await handle_subscription_halted(data)
        elif event == "subscription.cancelled":
            await handle_subscription_cancelled(data)

        return {"status": "ok"}

    except Exception as e:
        logger.exception("Webhook processing failed")
        raise HTTPException(status_code=500, detail="Webhook error")


# ======================================================
# PAYMENT CAPTURED (ONE-TIME PAYMENT)
# ======================================================

async def handle_payment_captured(data):
    try:
        payment_entity = data.get("payload", {}).get("payment", {}).get("entity", {})
        payment_id = payment_entity.get("id")
        notes = payment_entity.get("notes", {})

        telegram_id = int(notes.get("telegram_id"))
        channel_id = int(notes.get("channel_id"))
        validity_days = int(notes.get("validity_days"))
        amount = payment_entity.get("amount", 0) / 100

        now = datetime.now(timezone.utc)

        async with async_session() as db:
            # Fetch user
            user = await db.scalar(
                select(User).where(User.telegram_id == telegram_id)
            )
            if not user:
                logger.error("User not found for telegram_id=%s", telegram_id)
                return

            # Save payment record
            db.add(Payment(
                user_id=user.id,
                channel_id=channel_id,
                amount=amount,
                payment_id=payment_id,
                status="captured"
            ))
            await db.commit()

            # -------------------------------
            # USE NEW RENEWAL HANDLER
            # -------------------------------
            success = await handle_renewal_payment(db, payment_entity, notes)
            
            if not success:
                logger.error(f"Renewal handler failed for payment {payment_id}")
                return

            # Update user stats
            user.highest_amount_paid = max(user.highest_amount_paid or 0, amount)
            await db.commit()

            # Get channel for messaging
            channel = await db.get(Channel, channel_id)
            
            # Get updated membership for expiry date
            result = await db.execute(
                select(Membership).where(
                    and_(
                        Membership.user_id == user.id,
                        Membership.channel_id == channel_id,
                        Membership.is_active == True
                    )
                )
            )
            membership = result.scalar_one_or_none()
            
            if not membership:
                logger.error(f"No active membership found after payment")
                return
            
            expiry_str = membership.expiry_date.strftime("%d %b %Y")

            # -------------------------------
            # SEND INVITE LINK
            # -------------------------------
            try:
                invite = await bot.create_chat_invite_link(
                    int(channel.telegram_chat_id),
                    member_limit=1,
                    expire_date=now + timedelta(minutes=10)
                )

                await bot.send_message(
                    telegram_id,
                    f"✅ <b>Payment Successful!</b>\n\n"
                    f"💳 Amount: ₹{amount:.0f}\n"
                    f"📺 Channel: {channel.name}\n"
                    f"⏰ Valid until: {expiry_str}\n\n"
                    f"🔗 <b>Your Invite Link:</b>\n{invite.invite_link}\n\n"
                    f"⚠️ Link expires in 10 minutes",
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.error("Invite link failed: %s", e)
                await bot.send_message(
                    telegram_id,
                    f"✅ Payment successful for <b>{channel.name}</b>\n"
                    f"⏰ Valid until: {expiry_str}\n\n"
                    f"❌ Could not generate invite link. Contact admin.",
                    parse_mode="HTML"
                )

            # -------------------------------
            # AUTO-RENEW OFFER
            # -------------------------------
            await asyncio.sleep(2)

            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🔄 Enable Auto-Renewal",
                        callback_data=f"setup_autorenew_{user.id}_{channel_id}_{validity_days}"
                    )
                ]
            ])

            await bot.send_message(
                telegram_id,
                f"💰 <b>Never Miss Access!</b>\n\n"
                f"Enable Auto-Renewal for ₹{amount:.0f}/month\n\n"
                f"✅ Automatic payments\n"
                f"✅ Cancel anytime\n"
                f"✅ No interruptions",
                parse_mode="HTML",
                reply_markup=keyboard
            )

    except Exception as e:
        logger.exception("Payment capture handler failed")


# ======================================================
# SUBSCRIPTION EVENTS
# ======================================================

async def handle_subscription_authenticated(data):
    try:
        entity = data["payload"]["subscription"]["entity"]
        subscription_id = entity["id"]
        notes = entity.get("notes", {})

        user_id = int(notes["user_id"])
        channel_id = int(notes["channel_id"])

        async with async_session() as db:
            membership = await db.scalar(
                select(Membership).where(
                    Membership.user_id == user_id,
                    Membership.channel_id == channel_id
                )
            )
            if membership:
                membership.auto_renew_enabled = True
                membership.razorpay_subscription_id = subscription_id
                membership.subscription_status = "active"
                await db.commit()

    except Exception:
        logger.exception("Subscription authenticated error")


async def handle_subscription_charged(data):
    try:
        subscription_id = data["payload"]["subscription"]["entity"]["id"]

        async with async_session() as db:
            membership = await db.scalar(
                select(Membership).where(
                    Membership.razorpay_subscription_id == subscription_id
                )
            )
            if membership:
                membership.expiry_date += timedelta(days=membership.validity_days)
                await db.commit()

    except Exception:
        logger.exception("Subscription charged error")


async def handle_subscription_halted(data):
    try:
        subscription_id = data["payload"]["subscription"]["entity"]["id"]

        async with async_session() as db:
            membership = await db.scalar(
                select(Membership).where(
                    Membership.razorpay_subscription_id == subscription_id
                )
            )
            if membership:
                membership.subscription_status = "halted"
                await db.commit()

                user = await db.get(User, membership.user_id)
                channel = await db.get(Channel, membership.channel_id)

                await bot.send_message(
                    user.telegram_id,
                    f"⚠️ Auto-renewal payment failed for <b>{channel.name}</b>.\n"
                    f"Please check your payment method.",
                    parse_mode="HTML"
                )

    except Exception:
        logger.exception("Subscription halted error")


async def handle_subscription_cancelled(data):
    try:
        subscription_id = data["payload"]["subscription"]["entity"]["id"]

        async with async_session() as db:
            membership = await db.scalar(
                select(Membership).where(
                    Membership.razorpay_subscription_id == subscription_id
                )
            )
            if membership:
                membership.auto_renew_enabled = False
                membership.subscription_status = "cancelled"
                await db.commit()

    except Exception:
        logger.exception("Subscription cancelled error")