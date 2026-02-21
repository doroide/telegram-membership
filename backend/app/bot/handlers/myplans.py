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
            await message.answer("No active plans.")
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
        
        text = "📋 *Your Active Plans*\n\n"
        
        for m in memberships:
            channel = await session.get(Channel, m.channel_id)
            
            now = datetime.now(timezone.utc)
            days_left = (m.expiry_date - now).days
            expiry = f"{m.expiry_date.date()} ({days_left} days)"
            
            text += (
                f"📺 {channel.name}\n"
                f"⏰ Expiry: {expiry}\n\n"
            )
        
        await message.answer(text, parse_mode="Markdown")


@router.callback_query(F.data == "my_plans")
async def my_plans_button(callback: CallbackQuery):
    """Handle My Plans button click"""
    await callback.answer()
    await my_plans(callback.message)