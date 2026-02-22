from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from sqlalchemy import select
from datetime import datetime, timezone
from backend.app.db.session import async_session
from backend.app.db.models import User, Membership, Channel

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
        
        # Get ALL memberships for debugging
        all_result = await session.execute(
            select(Membership).where(Membership.user_id == user.id)
        )
        all_memberships = all_result.scalars().all()
        
        # Get active memberships
        result = await session.execute(
            select(Membership)
            .where(Membership.user_id == user.id)
            .where(Membership.is_active == True)
        )
        memberships = result.scalars().all()
        
        # Debug output
        debug = (
            f"🔍 Debug:\n"
            f"User ID: {user.id}\n"
            f"Telegram ID: {telegram_id}\n"
            f"Total memberships: {len(all_memberships)}\n"
            f"Active: {len(memberships)}\n"
        )
        
        if all_memberships:
            debug += "\nAll memberships:\n"
            for m in all_memberships:
                debug += f"- Channel {m.channel_id}: active={m.is_active}, expiry={m.expiry_date}\n"
        
        # Remove debug output for production
        # await message.answer(debug)
        
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