import os
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest
from sqlalchemy import select

from backend.app.db.session import async_session
from backend.app.db.models import Channel, User
from backend.app.services.payment_service import create_payment_link
from backend.app.services.tier_engine import (
    get_plans_for_user,
    format_plan_display
)

router = Router()


# =====================================================
# SHOW PRICING PLANS FOR SELECTED CHANNEL
# =====================================================

@router.callback_query(F.data.startswith("userch_"))
async def show_channel_plans(callback: CallbackQuery):
    """Show pricing plans when user selects a channel"""
    try:
        channel_id = int(callback.data.split("_")[1])
        
        async with async_session() as session:
            # Get channel
            channel_result = await session.execute(
                select(Channel).where(Channel.id == channel_id)
            )
            channel = channel_result.scalar_one_or_none()
            
            if not channel:
                await callback.answer("Channel not found", show_alert=True)
                return
            
            # Get user
            user_result = await session.execute(
                select(User).where(User.telegram_id == callback.from_user.id)
            )
            user = user_result.scalar_one_or_none()
            
            if not user:
                await callback.answer("User not found. Please start with /start", show_alert=True)
                return
            
            # Get plans based on user's tier
            plans = get_plans_for_user(user, channel_id)
            
            if not plans:
                await callback.answer("No plans available", show_alert=True)
                return
            
            # Determine tier display name
            if user.is_lifetime_member:
                tier_display = f"Lifetime Member (₹{user.lifetime_amount})"
            elif channel_id == 1 and user.channel_1_tier:
                tier_display = f"Tier {user.channel_1_tier}"
            else:
                tier_display = f"Tier {user.current_tier}"
            
            # Create buttons for each plan
            keyboard = []
            for index, plan in enumerate(plans):
                button_text = format_plan_display(plan)
                keyboard.append([
                    InlineKeyboardButton(
                        text=button_text,
                        callback_data=f"buy_{channel_id}_{plan['days']}_{plan['price']}"
                    )
                ])
            
            keyboard.append([
                InlineKeyboardButton(text="🔙 Back to Channels", callback_data="back_to_channels")
            ])
            
            try:
                await callback.message.edit_text(
                    f"📺 <b>{channel.name}</b>\n\n"
                    f"💎 Your Tier: {tier_display}\n\n"
                    f"Choose your subscription plan:",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
                    parse_mode="HTML"
                )
                await callback.answer()
            except TelegramBadRequest:
                # Message is same or query too old
                await callback.answer()
    
    except Exception as e:
        await callback.answer(f"Error: {str(e)}", show_alert=True)


# =====================================================
# HANDLE PLAN PURCHASE
# =====================================================
@router.callback_query(F.data.startswith("buy_"))
async def handle_plan_purchase(callback: CallbackQuery):
    """Create payment link when user selects a plan"""
    print("=" * 60)
    print("🎯 PAYMENT HANDLER TRIGGERED")
    print(f"   Callback data: {callback.data}")
    print(f"   User: {callback.from_user.id}")
    print("=" * 60)
    
    try:
        parts = callback.data.split("_")
        print(f"📦 Parsed parts: {parts}")
        
        channel_id = int(parts[1])
        validity_days = int(parts[2])
        amount = int(parts[3])
        
        print(f"✅ Parsed values:")
        print(f"   Channel ID: {channel_id}")
        print(f"   Validity days: {validity_days}")
        print(f"   Amount: {amount}")
        
        async with async_session() as session:
            # Get channel
            print(f"🔍 Looking up channel {channel_id}...")
            channel_result = await session.execute(
                select(Channel).where(Channel.id == channel_id)
            )
            channel = channel_result.scalar_one_or_none()
            
            if not channel:
                print(f"❌ Channel {channel_id} not found!")
                await callback.answer("Channel not found", show_alert=True)
                return
            
            print(f"✅ Found channel: {channel.name}")
            
            # Get user
            print(f"🔍 Looking up user {callback.from_user.id}...")
            user_result = await session.execute(
                select(User).where(User.telegram_id == callback.from_user.id)
            )
            user = user_result.scalar_one_or_none()
            
            if not user:
                print(f"❌ User {callback.from_user.id} not found!")
                await callback.answer("User not found", show_alert=True)
                return
            
            print(f"✅ Found user: ID={user.id}, Telegram ID={user.telegram_id}")
            
            # Format plan name
            validity_display = {
                30: "1 Month",
                90: "3 Months",
                120: "4 Months",
                180: "6 Months",
                365: "1 Year",
                730: "Lifetime"
            }.get(validity_days, f"{validity_days} days")
            
            print(f"💰 Creating payment link with:")
            print(f"   user_id: {user.id}")
            print(f"   telegram_id: {user.telegram_id}")
            print(f"   channel_id: {channel.id}")
            print(f"   days: {validity_days}")
            print(f"   price: {amount}")
            
            # Create payment link
            payment_link = await create_payment_link(
                user_id=user.id,
                telegram_id=user.telegram_id,
                channel_id=channel.id,
                days=validity_days,
                price=amount
            )
            
            print(f"✅ Payment link created: {payment_link}")
            
            # Send payment link
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💳 Pay Now", url=payment_link)],
                [InlineKeyboardButton(text="🔙 Back", callback_data=f"userch_{channel_id}")]
            ])
            
            try:
                await callback.message.edit_text(
                    f"💳 <b>Payment Details</b>\n\n"
                    f"📺 Channel: {channel.name}\n"
                    f"📦 Plan: {validity_display}\n"
                    f"💰 Amount: ₹{amount}\n\n"
                    f"Click the button below to complete payment:",
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
                print("✅ Message sent to user")
                await callback.answer()
            except TelegramBadRequest as e:
                print(f"⚠️ TelegramBadRequest: {e}")
                await callback.answer()
    
    except Exception as e:
        print("=" * 60)
        print(f"❌ CRITICAL ERROR in handle_plan_purchase:")
        print(f"   Error: {e}")
        print(f"   Type: {type(e).__name__}")
        import traceback
        print(f"   Traceback:")
        traceback.print_exc()
        print("=" * 60)
        await callback.answer(f"Error: {str(e)}", show_alert=True)


# =====================================================
# BACK TO CHANNELS
# =====================================================

@router.callback_query(F.data == "back_to_channels")
async def back_to_channels(callback: CallbackQuery):
    """Return to channel selection"""
    try:
        telegram_id = callback.from_user.id
        
        async with async_session() as session:
            # Get user
            user_result = await session.execute(
                select(User).where(User.telegram_id == telegram_id)
            )
            user = user_result.scalar_one_or_none()
            
            if not user:
                await callback.answer("User not found", show_alert=True)
                return
            
            # Get user's purchased channels
            from backend.app.db.models import Membership
            membership_result = await session.execute(
                select(Membership.channel_id)
                .where(Membership.user_id == user.id)
                .distinct()
            )
            purchased_channel_ids = [row[0] for row in membership_result.all()]
            
            # Get channels to display
            channel_result = await session.execute(
                select(Channel)
                .where(
                    Channel.is_active == True,
                    (Channel.is_public == True) | (Channel.id.in_(purchased_channel_ids))
                )
                .order_by(Channel.id)
            )
            channels = channel_result.scalars().all()
            
            if not channels:
                try:
                    await callback.message.edit_text(
                        "❌ No channels available at the moment.\n"
                        "Please check back later!"
                    )
                    await callback.answer()
                except TelegramBadRequest:
                    await callback.answer()
                return
            
            # Build keyboard
            keyboard = []
            for channel in channels:
                # Check if user has active membership
                has_active = False
                if channel.id in purchased_channel_ids:
                    membership_check = await session.execute(
                        select(Membership)
                        .where(
                            Membership.user_id == user.id,
                            Membership.channel_id == channel.id,
                            Membership.is_active == True
                        )
                    )
                    has_active = membership_check.scalar_one_or_none() is not None
                
                # Add status indicator
                if has_active:
                    status = "✅"
                elif channel.id in purchased_channel_ids:
                    status = "⏰"
                else:
                    status = "📺"
                
                keyboard.append([
                    InlineKeyboardButton(
                        text=f"{status} {channel.name}",
                        callback_data=f"userch_{channel.id}"
                    )
                ])
            
            keyboard.append([
                InlineKeyboardButton(text="📋 My Plans", callback_data="my_plans")
            ])
            
            try:
                await callback.message.edit_text(
                    "📺 <b>Available Channels</b>\n\n"
                    "✅ = Active subscription\n"
                    "⏰ = Expired (renew available)\n"
                    "📺 = New channel\n\n"
                    "Select a channel to view plans:",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
                    parse_mode="HTML"
                )
                await callback.answer()
            except TelegramBadRequest:
                # Message is same or query too old
                await callback.answer()
    
    except Exception as e:
        await callback.answer(f"Error: {str(e)}", show_alert=True)