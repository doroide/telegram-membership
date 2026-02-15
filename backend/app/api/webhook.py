from fastapi import APIRouter, Request, HTTPException
from sqlalchemy import select
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
        amount = payment_entity.get("amount", 0) / 100
        notes = payment_entity.get("notes", {})

        telegram_id = int(notes.get("telegram_id"))
        channel_id = int(notes.get("channel_id"))
        validity_days = int(notes.get("validity_days"))

        now = datetime.now(timezone.utc)

        async with async_session() as db:
            # Fetch user
            user = await db.scalar(
                select(User).where(User.telegram_id == telegram_id)
            )
            if not user:
                logger.error("User not found for telegram_id=%s", telegram_id)
                return

            # Save payment
            db.add(Payment(
                user_id=user.id,
                channel_id=channel_id,
                amount=amount,
                payment_id=payment_id,
                status="captured"
            ))

            # Fetch latest membership (active or expired)
            membership = await db.scalar(
                select(Membership)
                .where(
                    Membership.user_id == user.id,
                    Membership.channel_id == channel_id
                )
                .order_by(Membership.expiry_date.desc())
            )

            # -------------------------------
            # MEMBERSHIP LOGIC (FIXED)
            # -------------------------------
            if membership and membership.expiry_date > now:
                # Active → extend
                membership.expiry_date += timedelta(days=validity_days)
                membership.amount_paid += amount
            else:
                # Expired or new → reset clean
                if not membership:
                    membership = Membership(
                        user_id=user.id,
                        channel_id=channel_id,
                        tier=user.current_tier,
                        validity_days=validity_days,
                        amount_paid=amount,
                        start_date=now,
                        expiry_date=now + timedelta(days=validity_days),
                        is_active=True
                    )
                    db.add(membership)
                else:
                    membership.start_date = now
                    membership.expiry_date = now + timedelta(days=validity_days)
                    membership.amount_paid = amount
                    membership.is_active = True

            user.highest_amount_paid = max(user.highest_amount_paid or 0, amount)
            await db.commit()

            channel = await db.get(Channel, channel_id)
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
