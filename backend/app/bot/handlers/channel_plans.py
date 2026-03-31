import os
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest
from sqlalchemy import select

from backend.app.db.session import async_session
from backend.app.db.models import Channel, User
from backend.app.bot.handlers.upi_payment import show_upi_payment
from backend.app.services.tier_engine import (
    get_plans_for_user,
    format_plan_display
)

router = Router()

CHANNEL_EMOJIS = {
    12: "📺", 13: "🔥", 14: "🎬", 15: "📚",
    16: "🔞", 17: "💫", 18: "💎", 19: "🎭",
    20: "📸", 21: "🌶️"
}


# =====================================================
# SHOW PRICING PLANS FOR SELECTED CHANNEL
# =====================================================

@router.callback_query(F.data.startswith("userch_"))
async def show_channel_plans(callback: CallbackQuery):
    """Show pricing plans when user selects a channel"""
    try:
        channel_id = int(callback.data.split("_")[1])
        
        async with async_session() as session:
            channel_result = await session.execute(
                select(Channel).where(Channel.id == channel_id)
            )
            channel = channel_result.scalar_one_or_none()
            
            if not channel:
                await callback.answer("Channel not found", show_alert=True)
                return
            
            user_result = await session.execute(
                select(User).where(User.telegram_id == callback.from_user.id)
            )
            user = user_result.scalar_one_or_none()
            
            if not user:
                await callback.answer("User not found. Please start with /start", show_alert=True)
                return
            
            plans = await get_plans_for_user(user, channel_id, session)
            
            if not plans:
                await callback.answer("No plans available", show_alert=True)
                return
            
            keyboard = []

            if channel.is_public and channel.description:
                keyboard.append([
                    InlineKeyboardButton(
                        text="ℹ️ Channel Description",
                        callback_data=f"ch_desc_{channel_id}"
                    )
                ])

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
                    f"Choose your subscription plan:\n"
                    f"⚡ Instant access after payment",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
                    parse_mode="HTML"
                )
                await callback.answer()
            except TelegramBadRequest:
                await callback.answer()
    
    except Exception as e:
        await callback.answer(f"Error: {str(e)}", show_alert=True)


# =====================================================
# HANDLE PLAN PURCHASE
# =====================================================
@router.callback_query(F.data.startswith("buy_"))
async def handle_plan_purchase(callback: CallbackQuery, state: FSMContext):
    """Route to UPI payment when user selects a plan"""
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
            print(f"✅ Routing to UPI payment flow")

            await show_upi_payment(
                callback=callback,
                channel_id=channel.id,
                days=validity_days,
                price=amount,
                channel_name=channel.name,
                state=state
            )
    
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
            user_result = await session.execute(
                select(User).where(User.telegram_id == telegram_id)
            )
            user = user_result.scalar_one_or_none()
            
            if not user:
                await callback.answer("User not found", show_alert=True)
                return
            
            from backend.app.db.models import Membership
            membership_result = await session.execute(
                select(Membership.channel_id)
                .where(Membership.user_id == user.id)
                .distinct()
            )
            purchased_channel_ids = [row[0] for row in membership_result.all()]
            
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
            
            keyboard = []
            for idx, channel in enumerate(channels, 1):
                ch_emoji = CHANNEL_EMOJIS.get(channel.id, "📺")
                keyboard.append([
                    InlineKeyboardButton(
                        text=f"{idx}. {ch_emoji} {channel.name}",
                        callback_data=f"userch_{channel.id}"
                    )
                ])
            
            keyboard.append([
                InlineKeyboardButton(text="📋 My Plans", callback_data="my_plans")
            ])
            
            try:
                await callback.message.edit_text(
                    "📺 <b>Available Channels</b>\n\n"
                    "👇 Select a channel to view plans:",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
                    parse_mode="HTML"
                )
                await callback.answer()
            except TelegramBadRequest:
                await callback.answer()
    
    except Exception as e:
        await callback.answer(f"Error: {str(e)}", show_alert=True)


# =====================================================
# CHANNEL DESCRIPTION
# =====================================================

@router.callback_query(F.data.startswith("ch_desc_"))
async def show_channel_description(callback: CallbackQuery):
    try:
        channel_id = int(callback.data.split("_")[2])

        async with async_session() as session:
            channel_result = await session.execute(
                select(Channel).where(Channel.id == channel_id)
            )
            channel = channel_result.scalar_one_or_none()

            if not channel:
                await callback.answer("Channel not found", show_alert=True)
                return

            user_result = await session.execute(
                select(User).where(User.telegram_id == callback.from_user.id)
            )
            user = user_result.scalar_one_or_none()

            plans = get_plans_for_user(user, channel_id)

            keyboard = []
            for plan in plans:
                button_text = format_plan_display(plan)
                keyboard.append([
                    InlineKeyboardButton(
                        text=button_text,
                        callback_data=f"buy_{channel_id}_{plan['days']}_{plan['price']}"
                    )
                ])
            keyboard.append([
                InlineKeyboardButton(text="🔙 Back", callback_data=f"userch_{channel_id}")
            ])

            try:
                await callback.message.edit_text(
                    f"📺 <b>{channel.name}</b>\n\n"
                    f"{channel.description}\n\n"
                    f"Choose your subscription plan:",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
                    parse_mode="HTML"
                )
                await callback.answer()
            except TelegramBadRequest:
                await callback.answer()

    except Exception as e:
        await callback.answer(f"Error: {str(e)}", show_alert=True)