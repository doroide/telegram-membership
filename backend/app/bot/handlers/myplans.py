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


def verify_webhook_signature(payload: bytes, signature: str) -> bool:
    """Verify Razorpay webhook signature"""
    expected_signature = hmac.new(
        RAZORPAY_WEBHOOK_SECRET.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected_signature, signature)


@router.post("/webhook")
async def razorpay_webhook(request: Request):
    """Handle Razorpay webhook events"""
    try:
        payload = await request.body()
        signature = request.headers.get("X-Razorpay-Signature")
        
        if not verify_webhook_signature(payload, signature):
            logger.error("Invalid webhook signature")
            raise HTTPException(status_code=400, detail="Invalid signature")
        
        data = await request.json()
        event = data.get("event")
        
        logger.info(f"Received webhook event: {event}")
        
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
        logger.error(f"Webhook error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def handle_payment_captured(data):
    """Handle one-time payment"""
    try:
        payment_entity = data.get("payload", {}).get("payment", {}).get("entity", {})
        payment_id = payment_entity.get("id")
        amount = payment_entity.get("amount", 0) / 100
        notes = payment_entity.get("notes", {})
        
        telegram_id = int(notes.get("telegram_id"))
        channel_id = int(notes.get("channel_id"))
        validity_days = int(notes.get("validity_days"))
        
        async with async_session() as db:
            # Get user
            result = await db.execute(
                select(User).where(User.telegram_id == telegram_id)
            )
            user = result.scalar_one_or_none()
            if not user:
                return
            
            # Create payment
            payment = Payment(
                user_id=user.id,
                channel_id=channel_id,
                amount=amount,
                payment_id=payment_id,
                status="captured"
            )
            db.add(payment)
            
            # Get or create membership
            result = await db.execute(
                select(Membership).where(
                    Membership.user_id == user.id,
                    Membership.channel_id == channel_id,
                    Membership.is_active == True
                )
            )
            membership = result.scalar_one_or_none()
            
            now = datetime.now(timezone.utc)
            
            if membership and membership.expiry_date > now:
                membership.expiry_date = membership.expiry_date + timedelta(days=validity_days)
                membership.amount_paid += amount
            else:
                if membership:
                    membership.tier = user.current_tier
                    membership.validity_days = validity_days
                    membership.amount_paid = amount
                    membership.start_date = now
                    membership.expiry_date = now + timedelta(days=validity_days)
                    membership.is_active = True
                else:
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
            
            user.highest_amount_paid = max(user.highest_amount_paid or 0, amount)
            await db.commit()
            
            # Get channel
            channel = await db.get(Channel, channel_id)
            expiry_str = membership.expiry_date.strftime("%d %b %Y")
            
            # Send invite link (merged with success message)
            try:
                invite_link = await bot.create_chat_invite_link(
                    int(channel.telegram_chat_id),
                    member_limit=1,
                    expire_date=datetime.now(timezone.utc) + timedelta(minutes=10)
                )
                
                await bot.send_message(
                    telegram_id,
                    f"✅ <b>Payment Successful!</b>\n\n"
                    f"💳 Amount: ₹{amount:.0f}\n"
                    f"📺 Channel: {channel.name}\n"
                    f"⏰ Valid until: {expiry_str}\n\n"
                    f"🔗 <b>Your Invite Link:</b>\n"
                    f"{invite_link.invite_link}\n\n"
                    f"⚠️ Link expires in 10 minutes",
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.error(f"Invite link error: {e}")
                await bot.send_message(
                    telegram_id,
                    f"✅ <b>Payment Successful!</b>\n\n"
                    f"💳 Amount: ₹{amount:.0f}\n"
                    f"📺 Channel: {channel.name}\n"
                    f"⏰ Valid until: {expiry_str}\n\n"
                    f"❌ Error creating invite link. Contact admin.",
                    parse_mode="HTML"
                )
            
            # Auto-renewal offer (NO Maybe Later button)
            await asyncio.sleep(2)
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Enable Auto-Renewal", callback_data=f"setup_autorenew_{user.id}_{channel_id}_{validity_days}")]
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
        logger.error(f"Error in payment handler: {e}")


async def handle_subscription_authenticated(data):
    """Handle auto-renewal setup"""
    try:
        subscription_entity = data.get("payload", {}).get("subscription", {}).get("entity", {})
        subscription_id = subscription_entity.get("id")
        notes = subscription_entity.get("notes", {})
        
        user_id = int(notes.get("user_id"))
        channel_id = int(notes.get("channel_id"))
        
        async with async_session() as db:
            result = await db.execute(
                select(Membership).where(
                    Membership.user_id == user_id,
                    Membership.channel_id == channel_id,
                    Membership.is_active == True
                )
            )
            membership = result.scalar_one_or_none()
            
            if membership:
                membership.auto_renew_enabled = True
                membership.razorpay_subscription_id = subscription_id
                membership.subscription_status = "active"
                await db.commit()
    
    except Exception as e:
        logger.error(f"Error in subscription handler: {e}")


async def handle_subscription_charged(data):
    """Handle monthly renewal - SILENT"""
    try:
        subscription_entity = data.get("payload", {}).get("subscription", {}).get("entity", {})
        subscription_id = subscription_entity.get("id")
        
        async with async_session() as db:
            result = await db.execute(
                select(Membership).where(
                    Membership.razorpay_subscription_id == subscription_id
                )
            )
            membership = result.scalar_one_or_none()
            
            if membership:
                membership.expiry_date = membership.expiry_date + timedelta(days=membership.validity_days)
                await db.commit()
    
    except Exception as e:
        logger.error(f"Error in renewal handler: {e}")


async def handle_subscription_halted(data):
    """Handle payment failure"""
    try:
        subscription_entity = data.get("payload", {}).get("subscription", {}).get("entity", {})
        subscription_id = subscription_entity.get("id")
        
        async with async_session() as db:
            result = await db.execute(
                select(Membership).where(
                    Membership.razorpay_subscription_id == subscription_id
                )
            )
            membership = result.scalar_one_or_none()
            
            if membership:
                membership.subscription_status = "halted"
                await db.commit()
                
                user = await db.get(User, membership.user_id)
                channel = await db.get(Channel, membership.channel_id)
                
                await bot.send_message(
                    user.telegram_id,
                    f"⚠️ Auto-renewal payment failed for {channel.name}\n\n"
                    f"Please check your payment method.",
                    parse_mode="HTML"
                )
    
    except Exception as e:
        logger.error(f"Error in halted handler: {e}")


async def handle_subscription_cancelled(data):
    """Handle cancellation"""
    try:
        subscription_entity = data.get("payload", {}).get("subscription", {}).get("entity", {})
        subscription_id = subscription_entity.get("id")
        
        async with async_session() as db:
            result = await db.execute(
                select(Membership).where(
                    Membership.razorpay_subscription_id == subscription_id
                )
            )
            membership = result.scalar_one_or_none()
            
            if membership:
                membership.auto_renew_enabled = False
                membership.subscription_status = "cancelled"
                await db.commit()
    
    except Exception as e:
        logger.error(f"Error in cancel handler: {e}")