"""
COMPLETE webhook.py - Replace your entire backend/app/api/webhook.py with this
Handles all Razorpay webhook events with NO immediate upsell (comes on Day 5 instead)
"""

from fastapi import APIRouter, Request, HTTPException
from sqlalchemy import select
from datetime import datetime, timedelta, timezone
from backend.app.db.session import async_session
from backend.app.db.models import User, Channel, Membership, Payment
from backend.app.bot.bot import bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from backend.app.bot.handlers.autorenew import get_plan_price
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


@router.post("/razorpay")
async def razorpay_webhook(request: Request):
    """Handle Razorpay webhook events"""
    try:
        # Get payload and signature
        payload = await request.body()
        signature = request.headers.get("X-Razorpay-Signature")
        
        # Verify signature
        if not verify_webhook_signature(payload, signature):
            logger.error("Invalid webhook signature")
            raise HTTPException(status_code=400, detail="Invalid signature")
        
        # Parse data
        data = await request.json()
        event = data.get("event")
        
        logger.info(f"Received webhook event: {event}")
        
        # Handle different events
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
        else:
            logger.info(f"Unhandled event: {event}")
        
        return {"status": "ok"}
    
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def handle_payment_captured(data):
    """
    Handle one-time payment success
    Day 0: Show payment success + invite link + auto-renewal offer
    NO UPSELL HERE - that comes on Day 5
    """
    try:
        payment_entity = data.get("payload", {}).get("payment", {}).get("entity", {})
        payment_id = payment_entity.get("id")
        amount = payment_entity.get("amount", 0) / 100  # Convert paise to rupees
        notes = payment_entity.get("notes", {})
        
        user_id = int(notes.get("user_id"))
        channel_id = int(notes.get("channel_id"))
        validity_days = int(notes.get("validity_days"))
        tier = int(notes.get("tier"))
        
        # Check if this is an upsell payment
        is_upsell = notes.get("is_upsell") == "true"
        upsell_id = notes.get("upsell_id")
        
        async with async_session() as db:
            # Create payment record
            payment = Payment(
                user_id=user_id,
                channel_id=channel_id,
                amount=amount,
                payment_id=payment_id,
                status="captured"
            )
            db.add(payment)
            
            # Get user
            user = await db.get(User, user_id)
            telegram_id = user.telegram_id
            
            # Check for existing active membership
            result = await db.execute(
                select(Membership).where(
                    Membership.user_id == user_id,
                    Membership.channel_id == channel_id,
                    Membership.is_active == True
                )
            )
            membership = result.scalar_one_or_none()
            
            now = datetime.now(timezone.utc)
            
            if membership and membership.expiry_date > now:
                # Extend existing active membership
                old_expiry = membership.expiry_date
                membership.expiry_date = old_expiry + timedelta(days=validity_days)
                membership.amount_paid += amount
                logger.info(f"Extended membership for user {user_id}, channel {channel_id}")
            else:
                # Create new membership or reactivate expired one
                if membership:
                    # Reactivate expired membership
                    membership.tier = tier
                    membership.validity_days = validity_days
                    membership.amount_paid = amount
                    membership.start_date = now
                    membership.expiry_date = now + timedelta(days=validity_days)
                    membership.is_active = True
                    membership.reminded_7d = False
                    membership.reminded_1d = False
                    membership.reminded_expired = False
                else:
                    # Create brand new membership
                    membership = Membership(
                        user_id=user_id,
                        channel_id=channel_id,
                        tier=tier,
                        validity_days=validity_days,
                        amount_paid=amount,
                        start_date=now,
                        expiry_date=now + timedelta(days=validity_days),
                        is_active=True
                    )
                    db.add(membership)
                
                logger.info(f"Created new membership for user {user_id}, channel {channel_id}")
            
            # Update user stats
            user.highest_amount_paid = max(user.highest_amount_paid or 0, amount)
            
            # If this was an upsell payment, mark it as completed
            if is_upsell and upsell_id:
                from backend.app.db.models import UpsellAttempt
                upsell_attempt = await db.get(UpsellAttempt, int(upsell_id))
                if upsell_attempt:
                    upsell_attempt.accepted = True
                    logger.info(f"Marked upsell {upsell_id} as completed")
            
            await db.commit()
            
            # Get channel info
            channel = await db.get(Channel, channel_id)
            expiry_str = membership.expiry_date.strftime("%d %b %Y")
            
            # Send success message
            await bot.send_message(
                telegram_id,
                f"✅ <b>Payment Successful!</b>\n\n"
                f"💳 Amount: ₹{amount:.0f}\n"
                f"📺 Channel: {channel.name}\n"
                f"⏰ Valid until: {expiry_str}\n\n"
                f"🔗 Getting your invite link...",
                parse_mode="HTML"
            )
            
            # Generate and send invite link
            try:
                invite_link = await bot.create_chat_invite_link(
                    channel.telegram_chat_id,
                    member_limit=1,
                    expire_date=datetime.now(timezone.utc) + timedelta(minutes=10)
                )
                
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📞 Contact Admin", url=f"https://t.me/{ADMIN_USERNAME}")]
                ])
                
                await bot.send_message(
                    telegram_id,
                    f"🔗 <b>Your Invite Link</b>\n\n"
                    f"Click below to join:\n{invite_link.invite_link}\n\n"
                    f"⚠️ Link expires in 10 minutes",
                    parse_mode="HTML",
                    reply_markup=keyboard
                )
            except Exception as e:
                logger.error(f"Error creating invite link: {e}")
                await bot.send_message(
                    telegram_id,
                    f"❌ Error creating invite link. Please contact admin.\n\n"
                    f"📞 @{ADMIN_USERNAME}",
                    parse_mode="HTML"
                )
            
            # Wait 3 seconds before showing auto-renewal offer
            await asyncio.sleep(3)
            
            # ONLY show auto-renewal offer on Day 0
            # NO UPSELL HERE - that comes on Day 5 via scheduled task
            plan_info = get_plan_price(tier, validity_days)
            if plan_info:
                plan_id = plan_info["plan_id"]
                
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(
                        text="🔄 Enable Auto-Renewal", 
                        callback_data=f"autorenew_{user_id}_{channel_id}_{plan_id}_{validity_days}"
                    )],
                    [InlineKeyboardButton(text="⏭️ Maybe Later", callback_data="autorenew_skip")]
                ])
                
                await bot.send_message(
                    telegram_id,
                    f"💰 <b>Never Miss Access!</b>\n\n"
                    f"Enable Auto-Renewal for ₹{amount:.0f}/month\n\n"
                    f"✅ Automatic UPI payments\n"
                    f"✅ Cancel anytime in your UPI app\n"
                    f"✅ No payment interruptions",
                    parse_mode="HTML",
                    reply_markup=keyboard
                )
            
            logger.info(f"Payment captured and processed for user {telegram_id}")
    
    except Exception as e:
        logger.error(f"Error handling payment.captured: {e}")


async def handle_subscription_authenticated(data):
    """
    Handle subscription setup completion (first payment for auto-renewal)
    User has authorized UPI AutoPay
    """
    try:
        subscription_entity = data.get("payload", {}).get("subscription", {}).get("entity", {})
        subscription_id = subscription_entity.get("id")
        status = subscription_entity.get("status")
        notes = subscription_entity.get("notes", {})
        
        user_id = int(notes.get("user_id"))
        channel_id = int(notes.get("channel_id"))
        validity_days = int(notes.get("validity_days"))
        tier = int(notes.get("tier"))
        amount = subscription_entity.get("total_count", 0)
        
        async with async_session() as db:
            # Get membership
            result = await db.execute(
                select(Membership).where(
                    Membership.user_id == user_id,
                    Membership.channel_id == channel_id,
                    Membership.is_active == True
                )
            )
            membership = result.scalar_one_or_none()
            
            if membership:
                # Enable auto-renewal
                membership.auto_renew_enabled = True
                membership.razorpay_subscription_id = subscription_id
                membership.subscription_status = status
                membership.auto_renew_method = "upi"
                
                await db.commit()
                
                # Get user
                user = await db.get(User, user_id)
                channel = await db.get(Channel, channel_id)
                
                # Send confirmation (SILENT - no spam)
                await bot.send_message(
                    user.telegram_id,
                    f"✅ <b>Auto-Renewal Activated!</b>\n\n"
                    f"📺 Channel: {channel.name}\n"
                    f"🔄 Renews automatically every month\n"
                    f"💰 Amount: ₹{amount:.0f}\n\n"
                    f"You can cancel anytime in your UPI app (GPay/PhonePe/Paytm)",
                    parse_mode="HTML"
                )
                
                logger.info(f"Auto-renewal enabled for user {user_id}, channel {channel_id}")
    
    except Exception as e:
        logger.error(f"Error handling subscription.authenticated: {e}")


async def handle_subscription_charged(data):
    """
    Handle monthly auto-renewal charge
    This is SILENT - no notification to user (to avoid spam)
    """
    try:
        subscription_entity = data.get("payload", {}).get("subscription", {}).get("entity", {})
        subscription_id = subscription_entity.get("id")
        
        async with async_session() as db:
            # Find membership by subscription ID
            result = await db.execute(
                select(Membership).where(
                    Membership.razorpay_subscription_id == subscription_id,
                    Membership.is_active == True
                )
            )
            membership = result.scalar_one_or_none()
            
            if membership:
                # Extend expiry by validity_days
                membership.expiry_date = membership.expiry_date + timedelta(days=membership.validity_days)
                membership.subscription_status = "active"
                
                # Reset reminder flags
                membership.reminded_7d = False
                membership.reminded_1d = False
                membership.reminded_expired = False
                
                await db.commit()
                
                logger.info(f"Auto-renewal charge processed for membership {membership.id}")
                
                # SILENT RENEWAL - No notification to avoid spam
    
    except Exception as e:
        logger.error(f"Error handling subscription.charged: {e}")


async def handle_subscription_halted(data):
    """
    Handle auto-renewal payment failure
    Notify user to fix payment method
    """
    try:
        subscription_entity = data.get("payload", {}).get("subscription", {}).get("entity", {})
        subscription_id = subscription_entity.get("id")
        
        async with async_session() as db:
            result = await db.execute(
                select(Membership).where(
                    Membership.razorpay_subscription_id == subscription_id,
                    Membership.is_active == True
                )
            )
            membership = result.scalar_one_or_none()
            
            if membership:
                membership.subscription_status = "halted"
                await db.commit()
                
                # Get user and channel
                user = await db.get(User, membership.user_id)
                channel = await db.get(Channel, membership.channel_id)
                
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📞 Contact Admin", url=f"https://t.me/{ADMIN_USERNAME}")]
                ])
                
                # Notify user
                await bot.send_message(
                    user.telegram_id,
                    f"⚠️ <b>Auto-Renewal Payment Failed</b>\n\n"
                    f"📺 Channel: {channel.name}\n\n"
                    f"Your auto-renewal payment couldn't be processed. "
                    f"Please check your UPI app or contact admin.\n\n"
                    f"Your subscription is still active until expiry.",
                    parse_mode="HTML",
                    reply_markup=keyboard
                )
                
                logger.warning(f"Auto-renewal halted for membership {membership.id}")
    
    except Exception as e:
        logger.error(f"Error handling subscription.halted: {e}")


async def handle_subscription_cancelled(data):
    """
    Handle auto-renewal cancellation by user
    """
    try:
        subscription_entity = data.get("payload", {}).get("subscription", {}).get("entity", {})
        subscription_id = subscription_entity.get("id")
        
        async with async_session() as db:
            result = await db.execute(
                select(Membership).where(
                    Membership.razorpay_subscription_id == subscription_id,
                    Membership.is_active == True
                )
            )
            membership = result.scalar_one_or_none()
            
            if membership:
                membership.auto_renew_enabled = False
                membership.subscription_status = "cancelled"
                await db.commit()
                
                # Get user and channel
                user = await db.get(User, membership.user_id)
                channel = await db.get(Channel, membership.channel_id)
                
                # Notify user
                await bot.send_message(
                    user.telegram_id,
                    f"🔕 <b>Auto-Renewal Cancelled</b>\n\n"
                    f"📺 Channel: {channel.name}\n\n"
                    f"Your subscription will remain active until the expiry date. "
                    f"You can renew manually from /myplans",
                    parse_mode="HTML"
                )
                
                logger.info(f"Auto-renewal cancelled for membership {membership.id}")
    
    except Exception as e:
        logger.error(f"Error handling subscription.cancelled: {e}")