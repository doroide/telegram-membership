from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select, and_
from datetime import datetime, timezone
from backend.app.db.session import async_session
from backend.app.db.models import User, Membership, Channel, UpsellAttempt

router = Router()

@router.message(F.text == "/myplans")
async def my_plans(message: Message):
    telegram_id = message.from_user.id
    
    async with async_session() as session:
        # Get user
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            await message.answer(f"❌ User not found (telegram_id: {telegram_id})")
            return
        
        # Get active memberships
        result = await session.execute(
            select(Membership)
            .where(Membership.user_id == user.id)
            .where(Membership.is_active == True)
        )
        memberships = result.scalars().all()
        
        if not memberships:
            await message.answer("No active plans.")
            return
        
        text = "📋 *Your Subscriptions*\n\n"
        text += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        for m in memberships:
            channel = await session.get(Channel, m.channel_id)
            
            now = datetime.now(timezone.utc)
            days_left = (m.expiry_date - now).days
            expiry_date = m.expiry_date.strftime("%d %b %Y")
            
            auto_renew = "✅ Yes" if m.auto_renew_enabled else "❌ No"
            
            text += f"📺 *{channel.name}*\n"
            text += f"   ├ 📅 Expires: {expiry_date}\n"
            text += f"   ├ ⏳ {days_left} days remaining\n"
            text += f"   └ 🔄 Auto-Renew: {auto_renew}\n\n"
            text += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        text += f"✅ *{len(memberships)} active plan{'s' if len(memberships) > 1 else ''}*"
        
        await message.answer(text, parse_mode="Markdown")


@router.callback_query(F.data == "my_plans")
async def my_plans_button(callback: CallbackQuery):
    """Handle My Plans button click"""
    await callback.answer()
    
    telegram_id = callback.from_user.id
    
    async with async_session() as session:
        # Get user
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            await callback.message.answer(f"❌ User not found (telegram_id: {telegram_id})")
            return
        
        # Get active memberships
        result = await session.execute(
            select(Membership)
            .where(Membership.user_id == user.id)
            .where(Membership.is_active == True)
        )
        memberships = result.scalars().all()
        
        if not memberships:
            await callback.message.answer("No active plans.")
            return
        
        text = "📋 *Your Subscriptions*\n\n"
        text += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        for m in memberships:
            channel = await session.get(Channel, m.channel_id)
            
            now = datetime.now(timezone.utc)
            days_left = (m.expiry_date - now).days
            expiry_date = m.expiry_date.strftime("%d %b %Y")
            
            auto_renew = "✅ Yes" if m.auto_renew_enabled else "❌ No"
            
            text += f"📺 *{channel.name}*\n"
            text += f"   ├ 📅 Expires: {expiry_date}\n"
            text += f"   ├ ⏳ {days_left} days remaining\n"
            text += f"   └ 🔄 Auto-Renew: {auto_renew}\n\n"
            text += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        text += f"✅ *{len(memberships)} active plan{'s' if len(memberships) > 1 else ''}*"
        
        await callback.message.answer(text, parse_mode="Markdown")


@router.callback_query(F.data == "view_all_upsells")
async def view_all_upsells(callback: CallbackQuery):
    """Show all available upsell offers (auto + manual)"""
    await callback.answer()
    
    async with async_session() as session:
        # Get user
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            await callback.message.answer("User not found.")
            return
        
        # Get all upsells (both manual and automatic)
        result = await session.execute(
            select(UpsellAttempt).where(
                and_(
                    UpsellAttempt.user_id == user.id,
                    UpsellAttempt.accepted == False
                )
            )
        )
        upsells = result.scalars().all()
        
        if not upsells:
            await callback.message.answer("😊 No special offers available right now.")
            return
        
        # Build offers message
        msg = "🎁 *Your Exclusive Offers*\n\n"
        msg += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        keyboard_buttons = []
        
        for upsell in upsells:
            # Get channel
            channel = await session.get(Channel, upsell.channel_id)
            
            # Format durations
            duration_map = {30: "1 Month", 90: "3 Months", 120: "4 Months", 180: "6 Months", 365: "1 Year"}
            from_duration = duration_map.get(upsell.from_validity_days, f"{upsell.from_validity_days} days")
            to_duration = duration_map.get(upsell.to_validity_days, f"{upsell.to_validity_days} days")
            
            original_price = upsell.to_amount / 0.8  # Calculate from 20% discount
            discount_pct = (upsell.discount_amount / original_price) * 100
            
            # Show custom message if manual offer
            if upsell.is_manual and upsell.custom_message:
                msg += f"✨ *{upsell.custom_message}*\n\n"
            
            msg += f"📺 *{channel.name}*\n"
            msg += f"Upgrade: {from_duration} → {to_duration}\n"
            msg += f"💰 ~~₹{original_price:.0f}~~ → ₹{upsell.to_amount:.0f}\n"
            msg += f"💸 Save ₹{upsell.discount_amount:.0f} ({discount_pct:.0f}% OFF)\n"
            
            if upsell.is_manual:
                msg += f"🎁 *Special admin offer!*\n"
            
            msg += "\n━━━━━━━━━━━━━━━━━━━━\n\n"
            
            # Add button
            keyboard_buttons.append([
                InlineKeyboardButton(
                    text=f"✅ Accept - {channel.name}",
                    callback_data=f"upsell_accept_{upsell.id}"
                )
            ])
        
        keyboard_buttons.append([
            InlineKeyboardButton(text="❌ Close", callback_data="close_upsells")
        ])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        
        await callback.message.answer(msg, parse_mode="Markdown", reply_markup=keyboard)


@router.callback_query(F.data == "close_upsells")
async def close_upsells(callback: CallbackQuery):
    """Close upsells message"""
    await callback.answer("You can view offers anytime from /myplans")
    await callback.message.delete()