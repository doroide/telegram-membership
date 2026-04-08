from decimal import Decimal
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select, and_
from datetime import datetime, timezone, timedelta
from backend.app.db.session import async_session
from backend.app.db.models import User, Membership, Channel, UpsellAttempt
import logging

router = Router()
logger = logging.getLogger(__name__)

@router.message(F.text == "/myplans")
async def my_plans(message: Message):
    telegram_id = message.from_user.id
    
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            await message.answer(f"❌ User not found (telegram_id: {telegram_id})")
            return
        
        result = await session.execute(
            select(Membership)
            .where(Membership.user_id == user.id)
            .order_by(Membership.expiry_date.desc())
        )
        all_memberships = result.scalars().all()
        
        if not all_memberships:
            await message.answer("No plans found.")
            return
        
        now = datetime.now(timezone.utc)
        
        active_plans = []
        expiring_soon = []
        expired_plans = []
        
        for m in all_memberships:
            if not m.is_active or m.expiry_date <= now:
                expired_plans.append(m)
            else:
                days_left = (m.expiry_date - now).days
                if days_left > 15:
                    active_plans.append(m)
                else:
                    expiring_soon.append(m)
        
        text = "📋 *Your Subscriptions*\n\n"
        renew_buttons = []
        
        if active_plans:
            text += "━━━━━━━━━━━━━━━━━━━━\n"
            text += "✅ *ACTIVE*\n\n"
            
            for idx, m in enumerate(active_plans, 1):
                channel = await session.get(Channel, m.channel_id)
                days_left = (m.expiry_date - now).days
                expiry_date = m.expiry_date.strftime("%d %b %Y")
                auto_renew = "✅ Yes" if m.auto_renew_enabled else "❌ No"
                
                text += f"📺 *{idx}. {channel.name}*\n"
                text += f"📺 *{channel.name}*\n"
                text += f"   ├ 📅 Expires: {expiry_date}\n"
                text += f"   ├ ⏳ {days_left} days remaining\n"
                text += f"   └ 🔄 Auto-Renew: {auto_renew}\n\n"
            
            text += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        if expiring_soon:
            text += "━━━━━━━━━━━━━━━━━━━━\n"
            text += "⏰ *EXPIRING SOON*\n\n"
            
            for idx, m in enumerate(expiring_soon, 1):
                channel = await session.get(Channel, m.channel_id)
                days_left = (m.expiry_date - now).days
                expiry_date = m.expiry_date.strftime("%d %b %Y")
                auto_renew = "✅ Yes" if m.auto_renew_enabled else "❌ No"
                
                text += f"📺 *{idx}. {channel.name}*\n"
                text += f"📺 *{channel.name}*\n"
                text += f"   ├ 📅 Expires: {expiry_date}\n"
                text += f"   ├ ⏳ {days_left} days remaining\n"
                text += f"   └ 🔄 Auto-Renew: {auto_renew}\n\n"
                
                if days_left <= 7:
                    renew_buttons.append([
                        InlineKeyboardButton(
                            text=f"🔴 Renew Now - {channel.name}",
                            callback_data=f"quick_renew_{m.id}"
                        )
                    ])
                else:
                    renew_buttons.append([
                        InlineKeyboardButton(
                            text=f"⚡ Renew Available - {channel.name}",
                            callback_data=f"quick_renew_{m.id}"
                        )
                    ])
            
            text += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        if expired_plans:
            text += "━━━━━━━━━━━━━━━━━━━━\n"
            text += "❌ *EXPIRED*\n\n"

            for idx, m in enumerate(expired_plans[:5], 1):
                channel = await session.get(Channel, m.channel_id)
                expired_date = m.expiry_date.strftime("%d %b %Y")
                
                text += f"📺 {idx}. {channel.name}\n"
                text += f"   └ Expired: {expired_date}\n\n"
                
                renew_buttons.append([
                    InlineKeyboardButton(
                        text=f"🔴 Renew to regain access - {channel.name}",
                        callback_data=f"quick_renew_{m.id}"
                    )
                ])
            
            text += "━━━━━━━━━━━━━━━━━━━━"
        
        renew_buttons.append([
            InlineKeyboardButton(text="🏠 Back to Home", callback_data="menu_back_home")
        ])

        keyboard = InlineKeyboardMarkup(inline_keyboard=renew_buttons)
        await message.answer(text, parse_mode="Markdown", reply_markup=keyboard)


@router.callback_query(F.data == "my_plans")
async def my_plans_button(callback: CallbackQuery):
    """Handle My Plans button click"""
    try:
        await callback.answer()
    except:
        pass
    
    telegram_id = callback.from_user.id
    
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            await callback.message.answer(f"❌ User not found (telegram_id: {telegram_id})")
            return
        
        result = await session.execute(
            select(Membership)
            .where(Membership.user_id == user.id)
            .order_by(Membership.expiry_date.desc())
        )
        all_memberships = result.scalars().all()
        
        if not all_memberships:
            await callback.message.answer("No plans found.")
            return
        
        now = datetime.now(timezone.utc)
        
        active_plans = []
        expiring_soon = []
        expired_plans = []
        
        for m in all_memberships:
            if not m.is_active or m.expiry_date <= now:
                expired_plans.append(m)
            else:
                days_left = (m.expiry_date - now).days
                if days_left > 15:
                    active_plans.append(m)
                else:
                    expiring_soon.append(m)
        
        text = "📋 *Your Subscriptions*\n\n"
        renew_buttons = []
        
        if active_plans:
            text += "✅ *ACTIVE*\n\n"
            
            for m in active_plans:
                channel = await session.get(Channel, m.channel_id)
                days_left = (m.expiry_date - now).days
                expiry_date = m.expiry_date.strftime("%d %b %Y")
                auto_renew = "✅ Yes" if m.auto_renew_enabled else "❌ No"
                
                text += f"📺 *{channel.name}*\n"
                text += f"   ├ 📅 Expires: {expiry_date}\n"
                text += f"   ├ ⏳ {days_left} days remaining\n"
                text += f"   └ 🔄 Auto-Renew: {auto_renew}\n\n"
        
        if expiring_soon:
            text += "⏰ *EXPIRING SOON*\n\n"
            
            for m in expiring_soon:
                channel = await session.get(Channel, m.channel_id)
                days_left = (m.expiry_date - now).days
                expiry_date = m.expiry_date.strftime("%d %b %Y")
                auto_renew = "✅ Yes" if m.auto_renew_enabled else "❌ No"
                
                text += f"📺 *{channel.name}*\n"
                text += f"   ├ 📅 Expires: {expiry_date}\n"
                text += f"   ├ ⏳ {days_left} days remaining\n"
                text += f"   └ 🔄 Auto-Renew: {auto_renew}\n\n"
                
                if days_left <= 7:
                    renew_buttons.append([
                        InlineKeyboardButton(
                            text=f"🔴 Renew Now - {channel.name}",
                            callback_data=f"quick_renew_{m.id}"
                        )
                    ])
                else:
                    renew_buttons.append([
                        InlineKeyboardButton(
                            text=f"⚡ Renew Available - {channel.name}",
                            callback_data=f"quick_renew_{m.id}"
                        )
                    ])
        
        if expired_plans:
            text += "⌛ *EXPIRED*\n\n"
            
            for m in expired_plans[:5]:
                channel = await session.get(Channel, m.channel_id)
                expired_date = m.expiry_date.strftime("%d %b %Y")
                
                text += f"📺 {channel.name}\n"
                text += f"   └ Expired: {expired_date}\n\n"
                
                renew_buttons.append([
                    InlineKeyboardButton(
                        text=f"✅ Renew to regain access - {channel.name}",
                        callback_data=f"quick_renew_{m.id}"
                    )
                ])

        renew_buttons.append([
            InlineKeyboardButton(text="🏠 Back to Home", callback_data="menu_back_home")
        ])

        keyboard = InlineKeyboardMarkup(inline_keyboard=renew_buttons)
        await callback.message.answer(text, parse_mode="Markdown", reply_markup=keyboard)


@router.callback_query(F.data.startswith("quick_renew_"))
async def quick_renew(callback: CallbackQuery, state: FSMContext):
    """Handle Quick Renew — routes to UPI payment flow"""
    try:
        await callback.answer()
    except:
        pass
    
    try:
        membership_id = int(callback.data.split("_")[2])
        
        async with async_session() as db:
            membership = await db.get(Membership, membership_id)
            if not membership:
                await callback.message.answer("❌ Membership not found.")
                return
            
            user = await db.get(User, membership.user_id)
            channel = await db.get(Channel, membership.channel_id)

            from backend.app.bot.handlers.upi_payment import show_upi_payment
            await show_upi_payment(
                callback=callback,
                channel_id=channel.id,
                days=membership.validity_days,
                price=membership.amount_paid,
                channel_name=channel.name,
                state=state
            )

            logger.info(f"Quick renew (UPI): user {user.telegram_id}, membership {membership_id}")
    
    except Exception as e:
        logger.error(f"Error in quick_renew: {e}")
        await callback.message.answer("❌ Something went wrong. Please contact admin.")


@router.callback_query(F.data == "view_all_upsells")
async def view_all_upsells(callback: CallbackQuery):
    """Show all available upsell offers (auto + manual)"""
    
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()
        
        try:
            await callback.answer()
        except:
            pass
        
        if not user:
            await callback.message.answer("User not found.")
            return
        
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
            await callback.message.answer(
                "😊 No special offers available right now.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🏠 Back to Home", callback_data="menu_back_home")]
                ])
            )
            return
        
        msg = "⏳ *Launch Offer — Limited Time*\n\n"
        
        keyboard_buttons = []
        
        for upsell in upsells:
            channel = await session.get(Channel, upsell.channel_id)
            if not channel:
                continue

            duration_map = {30: "1 Month", 90: "3 Months", 120: "4 Months", 180: "6 Months", 365: "1 Year"}
            from_duration = duration_map.get(upsell.from_validity_days, f"{upsell.from_validity_days} days")
            to_duration = duration_map.get(upsell.to_validity_days, f"{upsell.to_validity_days} days")
            
            original_price = float(upsell.to_amount) / 0.8
            discount_pct = (float(upsell.discount_amount) / original_price) * 100
            
            if upsell.is_manual and upsell.custom_message:
                msg += f"✨ *{upsell.custom_message}*\n\n"
            
            msg += f"📺 *{channel.name}*\n"
            msg += f"📈 Upgrade Plan\n"
            msg += f"{from_duration} → {to_duration}\n"
            msg += f"💰 ₹{original_price:.0f} → ₹{float(upsell.to_amount):.0f}\n"
            msg += f"🎉 Save ₹{float(upsell.discount_amount):.0f} • {discount_pct:.0f}% OFF\n"
            
            if upsell.is_manual:
                msg += f"🎁 *Special admin offer!*\n"
            
            keyboard_buttons.append([
                InlineKeyboardButton(
                    text=f"✅ Accept - {channel.name}",
                    callback_data=f"upsell_accept_{upsell.id}"
                )
            ])

        # Add Back to Home button
        keyboard_buttons.append([
            InlineKeyboardButton(text="🏠 Back to Home", callback_data="menu_back_home")
        ])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        await callback.message.answer(msg, parse_mode="Markdown", reply_markup=keyboard)