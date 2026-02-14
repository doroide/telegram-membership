import os
import hmac
import hashlib
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Request, Header, HTTPException
from sqlalchemy import select

from backend.app.db.session import async_session
from backend.app.db.models import User, Membership, Channel, Payment
from backend.bot.bot import bot
from backend.app.services.tier_engine import update_user_tier, get_user_tier_for_channel

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

    # =====================================================
    # SUBSCRIPTION AUTHENTICATED (First payment + setup)
    # =====================================================
    if event == "subscription.authenticated":
        subscription_entity = data["payload"]["subscription"]["entity"]
        notes = subscription_entity.get("notes", {})
        
        subscription_id = subscription_entity["id"]
        membership_id = int(notes.get("membership_id"))
        telegram_id = int(notes.get("telegram_id"))
        
        async with async_session() as session:
            membership = await session.get(Membership, membership_id)
            user = await session.get(User, membership.user_id)
            channel = await session.get(Channel, membership.channel_id)
            
            if membership:
                membership.auto_renew_enabled = True
                membership.subscription_status = "active"
                membership.razorpay_subscription_id = subscription_id
                
                # Detect payment method from webhook
                payment_method = subscription_entity.get("payment_method", "")
                if "paytm" in payment_method.lower():
                    membership.auto_renew_method = "upi_paytm"
                elif "phonepe" in payment_method.lower():
                    membership.auto_renew_method = "upi_phonepe"
                else:
                    membership.auto_renew_method = "upi_gpay"
                
                await session.commit()
                
                # ✅ SEND SUCCESS MESSAGE (only on setup)
                try:
                    await bot.send_message(
                        chat_id=telegram_id,
                        text=(
                            f"✅ <b>Auto-Renewal Enabled!</b>\n\n"
                            f"📺 Channel: <b>{channel.name}</b>\n"
                            f"💰 Amount: ₹{membership.amount_paid}/month\n"
                            f"📅 Next billing: {membership.expiry_date.strftime('%d %b %Y')}\n\n"
                            f"<i>Manage AutoPay in your {membership.auto_renew_method.split('_')[1].title()} app</i>"
                        ),
                        parse_mode="HTML"
                    )
                except Exception as e:
                    print(f"⚠️ Could not send auto-renewal confirmation: {e}")
                
                print(f"✅ Subscription authenticated: {subscription_id}")
        
        return {"ok": True}
    
    # =====================================================
    # SUBSCRIPTION CHARGED (Auto-renewal success - SILENT)
    # =====================================================
    elif event == "subscription.charged":
        subscription_entity = data["payload"]["subscription"]["entity"]
        payment_entity = data["payload"]["payment"]["entity"]
        notes = subscription_entity.get("notes", {})
        
        membership_id = int(notes.get("membership_id"))
        user_id = int(notes.get("user_id"))
        telegram_id = int(notes.get("telegram_id"))
        channel_id = int(notes.get("channel_id"))
        
        amount = float(payment_entity.get("amount", 0)) / 100
        
        now = datetime.now(timezone.utc)
        
        async with async_session() as session:
            membership = await session.get(Membership, membership_id)
            
            if membership and membership.auto_renew_enabled:
                # Make expiry_date timezone-aware if needed
                membership_expiry = membership.expiry_date
                if membership_expiry.tzinfo is None:
                    membership_expiry = membership_expiry.replace(tzinfo=timezone.utc)
                
                # Extend membership
                if membership_expiry > now:
                    # Still active, extend from current expiry
                    membership.expiry_date = membership_expiry + timedelta(days=membership.validity_days)
                else:
                    # Expired, extend from now
                    membership.expiry_date = now + timedelta(days=membership.validity_days)
                
                membership.is_active = True
                
                # Reset reminder flags
                membership.reminded_7d = False
                membership.reminded_1d = False
                membership.reminded_expired = False
                
                # Save payment
                payment = Payment(
                    user_id=user_id,
                    channel_id=channel_id,
                    amount=amount,
                    payment_id=payment_entity.get("id", "unknown"),
                    status="captured"
                )
                session.add(payment)
                
                await session.commit()
                
                # 🔇 NO MESSAGE TO USER (Silent renewal)
                print(f"✅ Auto-renewal successful (silent): Membership {membership_id} extended to {membership.expiry_date}")
        
        return {"ok": True}
    
    # =====================================================
    # SUBSCRIPTION HALTED (Payment failed)
    # =====================================================
    elif event == "subscription.halted":
        subscription_entity = data["payload"]["subscription"]["entity"]
        notes = subscription_entity.get("notes", {})
        
        membership_id = int(notes.get("membership_id"))
        telegram_id = int(notes.get("telegram_id"))
        
        async with async_session() as session:
            membership = await session.get(Membership, membership_id)
            channel = await session.get(Channel, membership.channel_id)
            
            if membership:
                membership.subscription_status = "halted"
                await session.commit()
                
                # ⚠️ NOTIFY USER (Payment failed - they NEED to know)
                from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
                
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(
                        text="💳 Pay Manually",
                        callback_data=f"userch_{channel.id}"
                    )]
                ])
                
                try:
                    await bot.send_message(
                        chat_id=telegram_id,
                        text=(
                            f"⚠️ <b>Auto-Renewal Payment Failed</b>\n\n"
                            f"📺 Channel: <b>{channel.name}</b>\n"
                            f"💰 Amount: ₹{membership.amount_paid}\n\n"
                            f"Your subscription is still active until:\n"
                            f"📅 {membership.expiry_date.strftime('%d %b %Y')}\n\n"
                            f"Please pay manually to continue or update your payment method in your UPI app."
                        ),
                        reply_markup=keyboard,
                        parse_mode="HTML"
                    )
                except Exception as e:
                    print(f"⚠️ Could not send payment failed message: {e}")
                
                print(f"⚠️ Subscription halted: {membership_id}")
        
        return {"ok": True}
    
    # =====================================================
    # SUBSCRIPTION CANCELLED
    # =====================================================
    elif event == "subscription.cancelled":
        subscription_entity = data["payload"]["subscription"]["entity"]
        notes = subscription_entity.get("notes", {})
        
        membership_id = int(notes.get("membership_id"))
        
        async with async_session() as session:
            membership = await session.get(Membership, membership_id)
            
            if membership:
                membership.auto_renew_enabled = False
                membership.subscription_status = "cancelled"
                await session.commit()
                
                # 🔇 NO MESSAGE (User cancelled in UPI app or via bot)
                print(f"✅ Subscription cancelled: {membership_id}")
        
        return {"ok": True}

    # =====================================================
    # PAYMENT.CAPTURED (One-time payment)
    # =====================================================
    elif event == "payment.captured":
        # Get payment entity
        payment_entity = data["payload"]["payment"]["entity"]
        notes = payment_entity.get("notes", {})
        
        print(f"📝 Notes: {notes}")

        # ✅ FIXED: Parse notes and support both old (user_id) and new (telegram_id) format
        telegram_id = None
        user_id_from_notes = None
        
        try:
            # Try to get telegram_id directly (new format)
            if "telegram_id" in notes:
                telegram_id = int(notes["telegram_id"])
                print(f"✅ Found telegram_id in notes: {telegram_id}")
            elif "user_id" in notes:
                # Old format - we'll look up telegram_id from database
                user_id_from_notes = int(notes["user_id"])
                print(f"🔄 Old payment link detected with user_id: {user_id_from_notes}")
            else:
                print(f"❌ Neither telegram_id nor user_id found in notes")
                raise HTTPException(400, "Neither telegram_id nor user_id found in notes")
            
            channel_id = int(notes["channel_id"])
            validity_days = int(notes["validity_days"])
            
            # Amount might be in notes (new) or payment entity (old)
            if "amount" in notes:
                amount = float(notes["amount"])
            else:
                amount = float(payment_entity.get("amount", 0)) / 100  # Convert paise to rupees
                print(f"⚠️ Amount not in notes, using payment amount: ₹{amount}")
            
        except (KeyError, ValueError) as e:
            print(f"❌ Missing or invalid notes: {e}")
            raise HTTPException(400, f"Invalid notes: {e}")

        # ✅ FIX: Use timezone-aware datetime
        now = datetime.now(timezone.utc)
        expiry = now + timedelta(days=validity_days)
        
        # ✅ NEW: Determine if lifetime purchase
        is_lifetime = validity_days == 730

        async with async_session() as session:

            # =========================================
            # ✅ FIXED: Convert user_id to telegram_id if needed
            # =========================================
            if telegram_id is None and user_id_from_notes is not None:
                user_lookup = await session.execute(
                    select(User).where(User.id == user_id_from_notes)
                )
                temp_user = user_lookup.scalar_one_or_none()
                
                if not temp_user:
                    print(f"❌ User ID {user_id_from_notes} not found in database")
                    raise HTTPException(400, f"User ID {user_id_from_notes} not found")
                
                telegram_id = temp_user.telegram_id
                print(f"✅ Converted user_id {user_id_from_notes} to telegram_id {telegram_id}")

            # =========================================
            # GET OR CREATE USER
            # =========================================
            result = await session.execute(
                select(User).where(User.telegram_id == telegram_id)
            )
            user = result.scalar_one_or_none()

            if not user:
                # ✅ NEW: Create user with Tier 3 default
                user = User(
                    telegram_id=telegram_id,
                    current_tier=3,
                    highest_amount_paid=0
                )
                session.add(user)
                await session.flush()
                print(f"✅ Created user: {telegram_id} with Tier 3")

            # =========================================
            # ✅ NEW: UPDATE USER TIER
            # =========================================
            update_user_tier(user, int(amount), channel_id, is_lifetime)
            print(f"🎯 Updated user tier - Current: {user.current_tier}, Channel 1: {user.channel_1_tier}, Lifetime: {user.is_lifetime_member}")

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
            # ✅ NEW: GET TIER USED FOR THIS PURCHASE
            # =========================================
            tier_used = get_user_tier_for_channel(user, channel_id)
            print(f"💎 Tier used for this purchase: {tier_used}")

            # =========================================
            # MEMBERSHIP (extend or create)
            # =========================================
            result = await session.execute(
                select(Membership)
                .where(Membership.user_id == user.id)
                .where(Membership.channel_id == channel.id)
            )

            membership = result.scalar_one_or_none()

            # ✅ FIX: Handle both timezone-aware and timezone-naive expiry_date
            if membership:
                # Make expiry_date timezone-aware if it isn't already
                membership_expiry = membership.expiry_date
                if membership_expiry.tzinfo is None:
                    membership_expiry = membership_expiry.replace(tzinfo=timezone.utc)
                
                if membership_expiry > now:
                    # Extend existing membership
                    membership.expiry_date = membership_expiry + timedelta(days=validity_days)
                    membership.amount_paid += amount
                    membership.tier = tier_used
                    
                    # ✅ NEW: Reset reminder flags on renewal/extension
                    membership.reminded_7d = False
                    membership.reminded_1d = False
                    membership.reminded_expired = False
                    
                    print(f"📅 Extended membership until {membership.expiry_date}")
                else:
                    # Update expired membership
                    membership.start_date = now
                    membership.expiry_date = expiry
                    membership.amount_paid = amount
                    membership.is_active = True
                    membership.tier = tier_used
                    membership.validity_days = validity_days
                    
                    # ✅ NEW: Reset reminder flags on renewal
                    membership.reminded_7d = False
                    membership.reminded_1d = False
                    membership.reminded_expired = False
                    
                    print(f"🔄 Renewed expired membership until {expiry}")
            else:
                # Create new membership
                membership = Membership(
                    user_id=user.id,
                    channel_id=channel.id,
                    tier=tier_used,
                    validity_days=validity_days,
                    amount_paid=amount,
                    start_date=now,
                    expiry_date=expiry,
                    is_active=True,
                    # ✅ NEW: Initialize reminder flags
                    reminded_7d=False,
                    reminded_1d=False,
                    reminded_expired=False
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
            
            # ✅ NEW: Commit and refresh user to get updated tier values
            await session.commit()
            await session.refresh(user)
            await session.refresh(membership)
            
            print(f"💾 Saved payment: ₹{amount}")

        # =========================================
        # SEND INVITE LINK
        # =========================================
        try:
            # Create invite link with expiry (max 10 minutes from now for security)
            invite_expiry = int((now + timedelta(minutes=10)).timestamp())
            
            # Add timeout to avoid webhook hanging
            import asyncio
            
            invite_task = asyncio.create_task(
                bot.create_chat_invite_link(
                    chat_id=channel.telegram_chat_id,
                    member_limit=1,
                    expire_date=invite_expiry
                )
            )
            
            # Wait max 5 seconds for invite creation
            invite = await asyncio.wait_for(invite_task, timeout=5.0)
            
            # Enhanced message with tier info
            tier_message = ""
            if user.is_lifetime_member:
                tier_message = "\n💎 You are now a <b>Lifetime Member</b>!"
            elif user.current_tier == 4:
                tier_message = "\n💎 You've unlocked <b>Tier 4 (Elite)</b> pricing!"
            
            message_task = asyncio.create_task(
                bot.send_message(
                    chat_id=telegram_id,
                    text=(
                        f"✅ <b>Payment Successful!</b>\n\n"
                        f"📺 Channel: <b>{channel.name}</b>\n"
                        f"💰 Amount: ₹{amount}\n"
                        f"🗓 Valid till: <b>{expiry.strftime('%d %b %Y')}</b>"
                        f"{tier_message}\n\n"
                        f"👉 Join here (link expires in 10 mins):\n{invite.invite_link}"
                    ),
                    parse_mode="HTML"
                )
            )
            
            # Wait max 5 seconds for message sending
            await asyncio.wait_for(message_task, timeout=5.0)
            
            print(f"✅ Sent invite link to {telegram_id}")
            
        except asyncio.TimeoutError:
            print(f"⏱️ Timeout sending invite - Telegram API slow")
            # Payment already processed, just notify user without invite
            try:
                fallback_task = asyncio.create_task(
                    bot.send_message(
                        chat_id=telegram_id,
                        text=(
                            f"✅ <b>Payment Successful!</b>\n\n"
                            f"📺 Channel: <b>{channel.name}</b>\n"
                            f"💰 Amount: ₹{amount}\n"
                            f"🗓 Valid till: <b>{expiry.strftime('%d %b %Y')}</b>\n\n"
                            f"⚠️ Invite link generation timed out.\n"
                            f"Please use /myplans to see your subscription."
                        ),
                        parse_mode="HTML"
                    )
                )
                await asyncio.wait_for(fallback_task, timeout=3.0)
            except:
                print(f"❌ Could not send fallback message either")
                
        except Exception as e:
            print(f"❌ Error sending invite: {e}")
            # Payment already processed, send fallback message
            try:
                await bot.send_message(
                    chat_id=telegram_id,
                    text=(
                        f"✅ <b>Payment Successful!</b>\n\n"
                        f"📺 Channel: <b>{channel.name}</b>\n"
                        f"💰 Amount: ₹{amount}\n"
                        f"🗓 Valid till: <b>{expiry.strftime('%d %b %Y')}</b>\n\n"
                        f"⚠️ There was an issue generating your invite link.\n"
                        f"Please use /myplans to see your subscription."
                    ),
                    parse_mode="HTML"
                )
            except:
                print(f"❌ Could not send fallback message")
        
       # =========================================
    # OFFER AUTO-RENEWAL & UPSELL (async tasks)
    # =========================================
    if validity_days != 730:  # Don't offer for lifetime plans
        import asyncio
        from backend.app.bot.handlers.autorenew import offer_autorenew
        from backend.app.bot.handlers.upsell import offer_upsell
        
        # Offer auto-renewal first
        asyncio.create_task(offer_autorenew(telegram_id, membership.id, amount))
        
        # Then offer upsell after a short delay (5 seconds)
        async def delayed_upsell():
            await asyncio.sleep(5)
            await offer_upsell(telegram_id, membership.id, amount)
        
        asyncio.create_task(delayed_upsell())

        return {"ok": True}
    
    # =====================================================
    # IGNORE OTHER EVENTS
    # =====================================================
    else:
        print(f"⏭️ Ignoring event: {event}")
        return {"ignored": True}