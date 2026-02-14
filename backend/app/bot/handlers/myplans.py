import os
from datetime import datetime, timezone
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.app.db.session import async_session
from backend.app.db.models import User, Channel, Membership
from backend.app.services.payment_service import create_payment_link

router = Router()

# Admin contact username
ADMIN_USERNAME = "Doroide47"


# =====================================================
# /MYPLANS COMMAND
# =====================================================

@router.message(Command("myplans"))
async def myplans_command(message: Message):
    """Show user's all memberships (public + private channels)"""
    await show_user_plans(message.from_user.id, message=message)


@router.callback_query(F.data == "my_plans")
async def myplans_callback(callback: CallbackQuery):
    """Show user's all memberships via callback"""
    await show_user_plans(callback.from_user.id, callback=callback)


async def show_user_plans(telegram_id: int, message: Message = None, callback: CallbackQuery = None):
    """
    Display all user memberships
    Shows both public and private channel memberships
    """
    async with async_session() as session:
        # Get user
        user_result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = user_result.scalar_one_or_none()
        
        if not user:
            text = "❌ User not found. Please start with /start"
            if callback:
                await callback.answer(text, show_alert=True)
            else:
                await message.answer(text)
            return
        
        # Get all memberships (active and expired)
        memberships_result = await session.execute(
            select(Membership, Channel)
            .join(Channel, Membership.channel_id == Channel.id)
            .where(Membership.user_id == user.id)
            .order_by(Membership.is_active.desc(), Membership.expiry_date.desc())
        )
        memberships_data = memberships_result.all()
        
        if not memberships_data:
            text = (
                "📋 <b>My Plans</b>\n\n"
                "You don't have any subscriptions yet.\n\n"
                "Use /start to browse available channels!"
            )
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Back to Channels", callback_data="back_to_channels")],
                [InlineKeyboardButton(text="📞 Contact Admin", url=f"https://t.me/{ADMIN_USERNAME}")]
            ])
            
            if callback:
                try:
                    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
                    await callback.answer()
                except TelegramBadRequest:
                    await callback.answer()
            else:
                await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
            return
        
        # Build response with tier info
        tier_display = f"Tier {user.current_tier}"
        if user.is_lifetime_member:
            tier_display = f"Lifetime Member (₹{user.lifetime_amount})"
        
        response = (
            f"📋 <b>My Subscriptions</b>\n\n"
            f"💎 Your Tier: {tier_display}\n\n"
        )
        
        # Use timezone-aware datetime
        now = datetime.now(timezone.utc)
        active_plans = []
        expired_plans = []
        
        # Separate active and expired
        for membership, channel in memberships_data:
            # Comparing timezone-aware datetimes
            if membership.is_active and membership.expiry_date > now:
                active_plans.append((membership, channel))
            else:
                expired_plans.append((membership, channel))
        
        # Show active plans
        if active_plans:
            response += "✅ <b>Active Plans:</b>\n\n"
            for membership, channel in active_plans:
                days_left = (membership.expiry_date - now).days
                visibility = "🔓" if channel.is_public else "🔒"
                
                # Show auto-renewal status
                autorenew_status = ""
                if getattr(membership, 'auto_renew_enabled', False) and getattr(membership, 'subscription_status', '') == "active":
                    autorenew_status = "\n   🔄 <b>Auto-Renewal: ON</b>"
                
                response += (
                    f"{visibility} <b>{channel.name}</b>\n"
                    f"   • Expires: {membership.expiry_date.strftime('%d %b %Y')}\n"
                    f"   • Days left: {days_left}\n"
                    f"   • Amount: ₹{membership.amount_paid}"
                    f"{autorenew_status}\n\n"
                )
        
        # Show expired plans
        if expired_plans:
            response += "⏰ <b>Expired Plans:</b>\n\n"
            for membership, channel in expired_plans:
                visibility = "🔓" if channel.is_public else "🔒"
                
                response += (
                    f"{visibility} <b>{channel.name}</b>\n"
                    f"   • Expired: {membership.expiry_date.strftime('%d %b %Y')}\n"
                    f"   • Last paid: ₹{membership.amount_paid}\n\n"
                )
        
        # Build keyboard with quick actions
        keyboard = []
        
        # Add manage auto-renewal buttons for active plans with auto-renewal
        for membership, channel in active_plans:
            if getattr(membership, 'auto_renew_enabled', False) and getattr(membership, 'subscription_status', '') == "active":
                keyboard.append([
                    InlineKeyboardButton(
                        text=f"⚙️ Manage Auto-Renewal - {channel.name}",
                        callback_data=f"autorenew_manage_{membership.id}"
                    )
                ])
        
        # ✅ NEW: One-Click Renew buttons for expired plans
        if expired_plans:
            for membership, channel in expired_plans:
                keyboard.append([
                    InlineKeyboardButton(
                        text=f"⚡ Quick Renew - {channel.name}",
                        callback_data=f"quick_renew_{membership.id}"
                    )
                ])
        
        # Add extend buttons for active plans
        if active_plans:
            keyboard.append([
                InlineKeyboardButton(
                    text="➕ Extend Active Plans",
                    callback_data="extend_info"
                )
            ])
        
        keyboard.append([
            InlineKeyboardButton(text="🔙 Back to Channels", callback_data="back_to_channels")
        ])
        keyboard.append([
            InlineKeyboardButton(text="📞 Contact Admin", url=f"https://t.me/{ADMIN_USERNAME}")
        ])
        
        if callback:
            try:
                await callback.message.edit_text(
                    response,
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
                    parse_mode="HTML"
                )
                await callback.answer()
            except TelegramBadRequest:
                # Message is same or query too old, just answer callback
                await callback.answer()
        else:
            await message.answer(
                response,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
                parse_mode="HTML"
            )


# =====================================================
# ✅ NEW: QUICK RENEW (One-Click Renewal)
# =====================================================

@router.callback_query(F.data.startswith("quick_renew_"))
async def quick_renew(callback: CallbackQuery):
    """Quick renewal - creates payment link with last plan details"""
    
    membership_id = int(callback.data.split("_")[2])
    telegram_id = callback.from_user.id
    
    async with async_session() as session:
        # Get membership and related data
        membership_result = await session.execute(
            select(Membership, Channel, User)
            .join(Channel, Membership.channel_id == Channel.id)
            .join(User, Membership.user_id == User.id)
            .where(Membership.id == membership_id)
        )
        result = membership_result.first()
        
        if not result:
            await callback.answer("Membership not found", show_alert=True)
            return
        
        membership, channel, user = result
        
        # Use same plan details as last purchase
        validity_days = membership.validity_days
        
        # Calculate price based on current tier
        from backend.app.bot.handlers.autorenew import get_plan_price
        amount = get_plan_price(user.current_tier, validity_days)
        
        if amount == 0:
            await callback.answer("Error calculating price. Please use Browse Channels.", show_alert=True)
            return
        
        # Create payment link
        try:
            payment_link = create_payment_link(
                user_id=user.id,
                telegram_id=telegram_id,
                channel_id=channel.id,
                amount=amount,
                validity_days=validity_days
            )
            
            validity_display = {
                30: "1 Month",
                90: "3 Months",
                120: "4 Months",
                180: "6 Months",
                365: "1 Year"
            }.get(validity_days, f"{validity_days} days")
            
            await callback.message.edit_text(
                f"⚡ <b>Quick Renew - {channel.name}</b>\n\n"
                f"💰 Amount: ₹{amount}\n"
                f"⏱️ Validity: {validity_display}\n"
                f"💎 Your Tier: {user.current_tier}\n\n"
                f"👉 Pay here:\n{payment_link}\n\n"
                f"<i>Link expires in 10 minutes</i>",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 Back to My Plans", callback_data="my_plans")],
                    [InlineKeyboardButton(text="📞 Contact Admin", url=f"https://t.me/{ADMIN_USERNAME}")]
                ])
            )
            
            await callback.answer("✅ Payment link created!", show_alert=False)
            
        except Exception as e:
            print(f"Error creating payment link: {e}")
            await callback.answer("Error creating payment link. Please try again.", show_alert=True)


# =====================================================
# EXTEND INFO
# =====================================================

@router.callback_query(F.data == "extend_info")
async def extend_info_callback(callback: CallbackQuery):
    """Show info about extending active plans"""
    try:
        await callback.message.edit_text(
            "➕ <b>Extend Active Plans</b>\n\n"
            "To extend your active subscription:\n\n"
            "1. Go back to channels\n"
            "2. Select the channel you want to extend\n"
            "3. Purchase another plan\n\n"
            "⚠️ New validity will be added to your current expiry date!",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Back to My Plans", callback_data="my_plans")],
                [InlineKeyboardButton(text="📺 Browse Channels", callback_data="back_to_channels")]
            ]),
            parse_mode="HTML"
        )
        await callback.answer()
    except TelegramBadRequest:
        await callback.answer()