import os
from datetime import datetime, timezone, timedelta
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select

from backend.app.db.session import async_session
from backend.app.db.models import Membership, User, Channel
from backend.bot.bot import bot
from backend.app.services.payment_service import razorpay_client

router = Router()

# =====================================================
# RAZORPAY PLAN IDS (from environment variables)
# =====================================================

def get_plan_id(validity_days: int, tier: int) -> str:
    """Get Razorpay plan ID based on validity and tier"""
    # Map validity days to duration code
    duration_map = {
        30: "1M",
        90: "3M",
        120: "4M",
        180: "6M",
        365: "1Y"
    }
    
    duration = duration_map.get(validity_days)
    if not duration:
        return None
    
    # Environment variable name: RAZORPAY_PLAN_1M_T1, etc.
    env_var = f"RAZORPAY_PLAN_{duration}_T{tier}"
    plan_id = os.getenv(env_var)
    
    if not plan_id:
        print(f"⚠️ Plan ID not found for {env_var}")
    
    return plan_id


# =====================================================
# OFFER AUTORENEW AFTER PAYMENT
# =====================================================

async def offer_autorenew(user_telegram_id: int, membership_id: int):
    """Offer auto-renewal option after successful payment"""
    
    print(f"🔄 offer_autorenew called: user={user_telegram_id}, membership_id={membership_id}")
    
    try:
        async with async_session() as session:
            membership = await session.get(Membership, membership_id)
            
            if not membership:
                print(f"❌ Membership {membership_id} not found")
                return
            
            # Don't offer for lifetime plans
            if membership.validity_days == 730:
                print(f"⏭️ Skipping auto-renewal offer for lifetime plan")
                return
            
            # Don't offer if already enabled (safe check with getattr)
            if getattr(membership, 'auto_renew_enabled', False):
                print(f"⏭️ Auto-renewal already enabled for membership {membership_id}")
                return
            
            channel = await session.get(Channel, membership.channel_id)
            
            if not channel:
                print(f"❌ Channel not found for membership {membership_id}")
                return
            
            validity_display = {
                30: "Monthly",
                90: "Quarterly",
                120: "4 Months",
                180: "Half-Yearly",
                365: "Yearly"
            }.get(membership.validity_days, f"{membership.validity_days} days")
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="🔄 Enable Auto-Renewal",
                    callback_data=f"autorenew_enable_{membership_id}"
                )],
                [InlineKeyboardButton(
                    text="❌ No Thanks",
                    callback_data="autorenew_skip"
                )]
            ])
            
            await bot.send_message(
                chat_id=user_telegram_id,
                text=(
                    f"🔄 <b>Enable Auto-Renewal?</b>\n\n"
                    f"📺 Channel: <b>{channel.name}</b>\n"
                    f"💰 Amount: ₹{membership.amount_paid} {validity_display}\n\n"
                    f"<b>Benefits:</b>\n"
                    f"✅ Pay via GPay or PhonePe\n"
                    f"✅ Automatic renewal before expiry\n"
                    f"✅ Never lose access\n"
                    f"✅ Cancel anytime in your UPI app\n\n"
                    f"<i>You'll be charged ₹{membership.amount_paid} automatically {validity_display.lower()}. "
                    f"Manage AutoPay in your GPay/PhonePe settings.</i>"
                ),
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            
            print(f"✅ Auto-renewal offer sent to user {user_telegram_id}")
            
    except Exception as e:
        print(f"⚠️ Error in offer_autorenew: {e}")
        import traceback
        traceback.print_exc()


# =====================================================
# ENABLE AUTORENEW
# =====================================================

@router.callback_query(F.data.startswith("autorenew_enable_"))
async def enable_autorenew(callback: CallbackQuery):
    """Create Razorpay subscription for auto-renewal"""
    
    try:
        membership_id = int(callback.data.split("_")[2])
        
        async with async_session() as session:
            membership = await session.get(Membership, membership_id)
            user = await session.get(User, membership.user_id)
            channel = await session.get(Channel, membership.channel_id)
            
            if not membership or not user:
                await callback.answer("Error: Membership not found", show_alert=True)
                return
            
            # Get plan ID for this tier and validity
            plan_id = get_plan_id(membership.validity_days, membership.tier)
            
            if not plan_id:
                await callback.answer(
                    "Auto-renewal not available for this plan. Please contact admin.",
                    show_alert=True
                )
                return
            
            # Calculate total renewals (max 12 cycles or until 2 years)
            total_count = min(12, int(730 / membership.validity_days))
            
            # Create subscription
            subscription = razorpay_client.subscription.create({
                "plan_id": plan_id,
                "customer_notify": 1,
                "total_count": total_count,
                "quantity": 1,
                "payment_method": "emandate",  # ✅ UPI AutoPay only!
                "notes": {
                    "user_id": str(user.id),
                    "telegram_id": str(user.telegram_id),
                    "membership_id": str(membership_id),
                    "channel_id": str(channel.id)
                }
            })
            
            # Store subscription ID temporarily (will update status via webhook)
            # Use setattr for safety
            setattr(membership, 'razorpay_subscription_id', subscription["id"])
            setattr(membership, 'subscription_status', "pending")
            await session.commit()
            
            # Send authorization link
            await callback.message.edit_text(
                f"🔄 <b>Setup Auto-Renewal</b>\n\n"
                f"Click below to authorize auto-renewal:\n"
                f"👉 {subscription['short_url']}\n\n"
                f"<b>You'll be asked to:</b>\n"
                f"1️⃣ Select GPay or PhonePe\n"
                f"2️⃣ Enter UPI PIN\n"
                f"3️⃣ Approve auto-deduction\n\n"
                f"💰 First payment: ₹{membership.amount_paid} (today)\n"
                f"📅 Next billing: {membership.expiry_date.strftime('%d %b %Y')}\n\n"
                f"<i>Link expires in 10 minutes</i>",
                parse_mode="HTML"
            )
            
            print(f"✅ Subscription created: {subscription['id']}")
            
    except Exception as e:
        print(f"❌ Error creating subscription: {e}")
        import traceback
        traceback.print_exc()
        await callback.answer("Error setting up auto-renewal. Please try again.", show_alert=True)
    
    await callback.answer()


# =====================================================
# SKIP AUTORENEW
# =====================================================

@router.callback_query(F.data == "autorenew_skip")
async def skip_autorenew(callback: CallbackQuery):
    """User declined auto-renewal"""
    await callback.message.edit_text(
        "👍 No problem! You can enable auto-renewal later from /myplans",
        parse_mode="HTML"
    )
    await callback.answer()


# =====================================================
# MANAGE AUTORENEW (from /myplans)
# =====================================================

@router.callback_query(F.data.startswith("autorenew_manage_"))
async def manage_autorenew(callback: CallbackQuery):
    """Show auto-renewal management options"""
    
    membership_id = int(callback.data.split("_")[2])
    
    async with async_session() as session:
        membership = await session.get(Membership, membership_id)
        channel = await session.get(Channel, membership.channel_id)
        
        if not membership:
            await callback.answer("Membership not found", show_alert=True)
            return
        
        # Safe attribute access
        subscription_status = getattr(membership, 'subscription_status', 'unknown')
        
        status_text = {
            "active": "✅ Active",
            "paused": "⏸ Paused",
            "cancelled": "❌ Cancelled",
            "halted": "⚠️ Payment Failed",
            "pending": "⏳ Pending Setup"
        }.get(subscription_status, "Unknown")
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="❌ Cancel Auto-Renewal",
                callback_data=f"autorenew_cancel_{membership_id}"
            )],
            [InlineKeyboardButton(
                text="🔙 Back",
                callback_data="my_plans"
            )]
        ])
        
        await callback.message.edit_text(
            f"🔄 <b>Auto-Renewal Settings</b>\n\n"
            f"📺 Channel: <b>{channel.name}</b>\n"
            f"💰 Amount: ₹{membership.amount_paid}\n"
            f"📅 Next billing: {membership.expiry_date.strftime('%d %b %Y')}\n"
            f"🔄 Status: {status_text}\n\n"
            f"<i>💡 You can also manage AutoPay directly in your GPay/PhonePe app:\n"
            f"Settings → AutoPay → Telegram Bot</i>",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    
    await callback.answer()


# =====================================================
# CANCEL AUTORENEW
# =====================================================

@router.callback_query(F.data.startswith("autorenew_cancel_"))
async def cancel_autorenew(callback: CallbackQuery):
    """Cancel auto-renewal subscription"""
    
    membership_id = int(callback.data.split("_")[2])
    
    async with async_session() as session:
        membership = await session.get(Membership, membership_id)
        
        # Safe attribute access
        subscription_id = getattr(membership, 'razorpay_subscription_id', None)
        
        if not membership or not subscription_id:
            await callback.answer("No active auto-renewal found", show_alert=True)
            return
        
        try:
            # Cancel in Razorpay
            razorpay_client.subscription.cancel(subscription_id)
            
            # Update database using setattr for safety
            setattr(membership, 'auto_renew_enabled', False)
            setattr(membership, 'subscription_status', "cancelled")
            await session.commit()
            
            await callback.message.edit_text(
                f"✅ <b>Auto-Renewal Cancelled</b>\n\n"
                f"Your current subscription remains active until:\n"
                f"📅 {membership.expiry_date.strftime('%d %b %Y')}\n\n"
                f"After that, you'll need to renew manually.",
                parse_mode="HTML"
            )
            
            print(f"✅ Cancelled subscription: {subscription_id}")
            
        except Exception as e:
            print(f"❌ Error cancelling subscription: {e}")
            import traceback
            traceback.print_exc()
            await callback.answer("Error cancelling auto-renewal. Please try again.", show_alert=True)
    
    await callback.answer()