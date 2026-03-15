from decimal import Decimal
from aiogram import Router, F
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
        # Get user
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            await message.answer(f"❌ User not found (telegram_id: {telegram_id})")
            return
        
        # Get ALL memberships for categorization
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
        
        # Categorize memberships into three states
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
        
        # Build message
        text = "📋 *Your Subscriptions*\n\n"
        renew_buttons = []
        
        # ACTIVE SECTION (>15 days) - NO RENEW BUTTON
        if active_plans:
            text += "━━━━━━━━━━━━━━━━━━━━\n"
            text += "✅ *ACTIVE*\n\n"
            
            for idx, m in enumerate(active_plans, 1):
                channel = await session.get(Channel, m.channel_id)
                days_left = (m.expiry_date - now).days
                expiry_date = m.expiry_date.strftime("%d %b %Y")
                auto_renew = "✅ Yes" if m.auto_renew_enabled else "❌ No"
                total_days = m.validity_days or 30
                progress = min(int((days_left / total_days) * 10), 10)
                bar = "🟢" * progress + "⬜" * (10 - progress)
                
                text += f"📺 *{idx}. {channel.name}*\n"
                text += f"   {bar}\n"
                text += f"   ├ 📅 Expires: {expiry_date}\n"
                text += f"   ├ ⏳ {days_left} days remaining\n"
                text += f"   └ 🔄 Auto-Renew: {auto_renew}\n\n"
            
            text += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        # EXPIRING SOON SECTION (1-15 days) - WITH RENEW BUTTON
        if expiring_soon:
            text += "━━━━━━━━━━━━━━━━━━━━\n"
            text += "⏰ *EXPIRING SOON*\n\n"
            
           for idx, m in enumerate(expiring_soon, 1):
                channel = await session.get(Channel, m.channel_id)
                days_left = (m.expiry_date - now).days
                expiry_date = m.expiry_date.strftime("%d %b %Y")
                auto_renew = "✅ Yes" if m.auto_renew_enabled else "❌ No"
                total_days = m.validity_days or 30
                progress = min(int((days_left / total_days) * 10), 10)
                bar = "🟡" * progress + "⬜" * (10 - progress)
                
                text += f"📺 *{idx}. {channel.name}*\n"
                text += f"   {bar}\n"
                text += f"   ├ 📅 Expires: {expiry_date}\n"
                text += f"   ├ ⏳ {days_left} days remaining\n"
                text += f"   └ 🔄 Auto-Renew: {auto_renew}\n\n"
                
                # Add urgency-based button
                if days_left <= 7:
                    # 1-7 days: URGENT
                    renew_buttons.append([
                        InlineKeyboardButton(
                            text=f"🔴 Renew Now - {channel.name}",
                            callback_data=f"quick_renew_{m.id}"
                        )
                    ])
                else:
                    # 8-15 days: NORMAL
                    renew_buttons.append([
                        InlineKeyboardButton(
                            text=f"⚡ Renew Available - {channel.name}",
                            callback_data=f"quick_renew_{m.id}"
                        )
                    ])
            
            text += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        # EXPIRED SECTION - WITH RENEW BUTTON
        if expired_plans:
            text += "━━━━━━━━━━━━━━━━━━━━\n"
            text += "❌ *EXPIRED*\n\n"

            for idx, m in enumerate(expired_plans[:5], 1):  # Show max 5
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
        
        # Send with renew buttons if any
        if renew_buttons:
            keyboard = InlineKeyboardMarkup(inline_keyboard=renew_buttons)
            await message.answer(text, parse_mode="Markdown", reply_markup=keyboard)
        else:
            await message.answer(text, parse_mode="Markdown")


@router.callback_query(F.data == "my_plans")
async def my_plans_button(callback: CallbackQuery):
    """Handle My Plans button click"""
    try:
        await callback.answer()
    except:
        pass
    
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
        
        # Get ALL memberships
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
        
        # Categorize memberships
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
        
        total = len(active_plans) + len(expiring_soon)
        expiring_count = len(expiring_soon)
        expired_count = len(expired_plans)

        text = f"📋 *Your Subscriptions*\n"
        text += f"✅ Active: {len(active_plans)}  ⚠️ Expiring: {expiring_count}  ❌ Expired: {expired_count}\n\n"
        renew_buttons = []
        
        # ACTIVE SECTION (>15 days) - NO RENEW BUTTON
        if active_plans:
            text += "━━━━━━━━━━━━━━━━━━━━\n"
            text += f"✅ *ACTIVE* ({len(active_plans)})\n\n"
            
              for idx, m in enumerate(active_plans, 1):
                channel = await session.get(Channel, m.channel_id)
                days_left = (m.expiry_date - now).days
                expiry_date = m.expiry_date.strftime("%d %b %Y")
                auto_renew = "✅ Yes" if m.auto_renew_enabled else "❌ No"
                total_days = m.validity_days or 30
                progress = min(int((days_left / total_days) * 10), 10)
                bar = "🟢" * progress + "⬜" * (10 - progress)
                
                text += f"📺 *{idx}. {channel.name}*\n"
                text += f"   {bar}\n"
                text += f"   ├ 📅 Expires: {expiry_date}\n"
                text += f"   ├ ⏳ {days_left} days remaining\n"
                text += f"   └ 🔄 Auto-Renew: {auto_renew}\n\n"
            
            text += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        # EXPIRING SOON SECTION
       # EXPIRING SOON SECTION
        if expiring_soon:
            text += "━━━━━━━━━━━━━━━━━━━━\n"
            text += f"⚠️ *EXPIRING SOON* ({len(expiring_soon)})\n\n"
            
            for idx, m in enumerate(expiring_soon, 1):
                channel = await session.get(Channel, m.channel_id)
                days_left = (m.expiry_date - now).days
                expiry_date = m.expiry_date.strftime("%d %b %Y")
                auto_renew = "✅ Yes" if m.auto_renew_enabled else "❌ No"
                total_days = m.validity_days or 30
                progress = min(int((days_left / total_days) * 10), 10)
                bar = "🟡" * progress + "⬜" * (10 - progress)
                
                text += f"📺 *{idx}. {channel.name}*\n"
                text += f"   {bar}\n"
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
        
        # EXPIRED SECTION
        if expired_plans:
            text += "━━━━━━━━━━━━━━━━━━━━\n"
            text += "❌ *EXPIRED*\n\n"
            
            for m in expired_plans[:5]:
                channel = await session.get(Channel, m.channel_id)
                expired_date = m.expiry_date.strftime("%d %b %Y")
                
                text += f"📺 {channel.name}\n"
                text += f"   └ Expired: {expired_date}\n\n"
                
                renew_buttons.append([
                    InlineKeyboardButton(
                        text=f"🔴 Renew to regain access - {channel.name}",
                        callback_data=f"quick_renew_{m.id}"
                    )
                ])
            
            text += "━━━━━━━━━━━━━━━━━━━━"
        
        if renew_buttons:
            keyboard = InlineKeyboardMarkup(inline_keyboard=renew_buttons)
            await callback.message.answer(text, parse_mode="Markdown", reply_markup=keyboard)
        else:
            await callback.message.answer(text, parse_mode="Markdown")


@router.callback_query(F.data.startswith("quick_renew_"))
async def quick_renew(callback: CallbackQuery):
    """Handle Quick Renew with grace period logic"""
    
    try:
        await callback.answer()
    except:
        pass
    
    try:
        membership_id = int(callback.data.split("_")[2])
        
        async with async_session() as db:
            # Get membership
            membership = await db.get(Membership, membership_id)
            if not membership:
                await callback.message.answer("❌ Membership not found.")
                return
            
            # Get user and channel
            user = await db.get(User, membership.user_id)
            channel = await db.get(Channel, membership.channel_id)
            
            # Calculate price
            base_prices = {
                1: {30: 49, 90: 149, 180: 299, 365: 599},
                2: {30: 99, 90: 299, 180: 599, 365: 1199},
                3: {30: 199, 90: 599, 180: 1199, 365: 2399},
                4: {30: 299, 90: 899, 180: 1799, 365: 3599},
            }
            
            tier = membership.tier or user.current_tier
            price = base_prices.get(tier, base_prices[3])[membership.validity_days]
            
            duration_map = {30: "1 Month", 90: "3 Months", 120: "4 Months", 180: "6 Months", 365: "1 Year"}
            duration = duration_map.get(membership.validity_days, f"{membership.validity_days} days")
            
            # Create payment link
            import razorpay
            import os
            
            razorpay_client = razorpay.Client(
                auth=(os.getenv("RAZORPAY_KEY"), os.getenv("RAZORPAY_SECRET"))
            )
            
            payment_data = {
                "amount": int(price * 100),
                "currency": "INR",
                "description": f"Renew: {channel.name} - {duration}",
                "customer": {
                    "name": user.full_name or "User",
                    "contact": str(user.telegram_id)
                },
                "notify": {"sms": False, "email": False},
                "reminder_enable": False,
                "notes": {
                    "telegram_id": str(user.telegram_id),
                    "channel_id": str(channel.id),
                    "validity_days": str(membership.validity_days),
                    "tier": str(tier),
                    "is_renewal": "true",  # Flag for webhook
                    "old_membership_id": str(membership.id)  # Reference to old membership
                }
            }
            
            response = razorpay_client.payment_link.create(payment_data)
            payment_link = response["short_url"]
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💳 Pay Now", url=payment_link)],
                [InlineKeyboardButton(text="📞 Contact Admin", url="https://t.me/Doroide47")]
            ])
            
            # Check if within grace period
            now = datetime.now(timezone.utc)
            grace_period_end = membership.expiry_date + timedelta(hours=48)
            within_grace = membership.expiry_date < now <= grace_period_end
            
            grace_msg = "\n\n⏰ *Grace Period Active!*\nRenewal will extend from your old expiry date." if within_grace else ""
            
            await callback.message.edit_text(
                f"⚡ *Quick Renew*\n\n"
                f"📺 Channel: {channel.name}\n"
                f"📅 Duration: {duration}\n"
                f"💰 Price: ₹{price}\n\n"
                f"Click 'Pay Now' to renew!{grace_msg}",
                parse_mode="Markdown",
                reply_markup=keyboard
            )
            
            logger.info(f"Quick renew: user {user.telegram_id}, membership {membership_id}, grace={within_grace}")
    
    except Exception as e:
        logger.error(f"Error in quick_renew: {e}")
        await callback.message.answer("❌ Something went wrong. Please contact admin.")


@router.callback_query(F.data == "view_all_upsells")
async def view_all_upsells(callback: CallbackQuery):
    """Show all available upsell offers (auto + manual)"""
    
    async with async_session() as session:
        # Get user
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
            if not channel:
                continue  # Skip upsells for deleted/missing channels

            
            # Format durations
            duration_map = {30: "1 Month", 90: "3 Months", 120: "4 Months", 180: "6 Months", 365: "1 Year"}
            from_duration = duration_map.get(upsell.from_validity_days, f"{upsell.from_validity_days} days")
            to_duration = duration_map.get(upsell.to_validity_days, f"{upsell.to_validity_days} days")
            
            original_price = float(upsell.to_amount) / 0.8  # Calculate from 20% discount
            discount_pct = (float(upsell.discount_amount) / original_price) * 100
            
            # Show custom message if manual offer
            if upsell.is_manual and upsell.custom_message:
                msg += f"✨ *{upsell.custom_message}*\n\n"
            
            msg += f"📺 *{channel.name}*\n"
            msg += f"Upgrade: {from_duration} → {to_duration}\n"
            msg += f"💰 ~~₹{original_price:.0f}~~ → ₹{float(upsell.to_amount):.0f}\n"
            msg += f"💸 Save ₹{float(upsell.discount_amount):.0f} ({discount_pct:.0f}% OFF)\n"
            
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
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        
        await callback.message.answer(msg, parse_mode="Markdown", reply_markup=keyboard)