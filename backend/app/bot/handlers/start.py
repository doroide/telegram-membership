import os
from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.app.db.session import async_session
from backend.app.db.models import User, Channel, Membership

router = Router()

# Admin contact username
ADMIN_USERNAME = "Doroide47"


# =====================================================
# /START COMMAND
# =====================================================

@router.message(Command("start"))
async def start_command(message: Message):
    """
    Show available channels to user
    
    Display logic:
    - Always show 4 public channels
    - Show purchased private channels (for renewal)
    - Hide unpurchased private channels
    """
    telegram_id = message.from_user.id
    
    async with async_session() as session:
        # Get or create user
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            # Create new user with Tier 3 default
            user = User(
                telegram_id=telegram_id,
                username=message.from_user.username,
                full_name=message.from_user.full_name,
                current_tier=3
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
        
        # Get user's purchased channels
        membership_result = await session.execute(
            select(Membership.channel_id)
            .where(Membership.user_id == user.id)
            .distinct()
        )
        purchased_channel_ids = [row[0] for row in membership_result.all()]
        
        # Get channels to display
        # 1. All public channels (channels 1-4)
        # 2. Private channels user has purchased
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
            await message.answer(
                "❌ No channels available at the moment.\n"
                "Please check back later!"
            )
            return
        
        # Build channel selection keyboard
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
                status = "⏰"  # Expired
            else:
                status = "📺"  # New
            
            keyboard.append([
                InlineKeyboardButton(
                    text=f"{status} {channel.name}",
                    callback_data=f"userch_{channel.id}"
                )
            ])
        
        # Add My Plans and Contact Admin buttons
        keyboard.append([
            InlineKeyboardButton(text="📋 My Plans", callback_data="my_plans")
        ])

        keyboard.append([
            InlineKeyboardButton(text="🎁 Offers for You", callback_data="view_all_upsells")}
        ])
        keyboard.append([
            InlineKeyboardButton(text="📞 Contact Admin", url=f"https://t.me/{ADMIN_USERNAME}")
        ])
        
        welcome_message = (
            f"👋 <b>Welcome{' back' if user.id else ''}, {message.from_user.first_name}!</b>\n\n"
            f"📺 Available channels:\n\n"
            f"✅ = Active subscription\n"
            f"⏰ = Expired (renew available)\n"
            f"📺 = New channel\n\n"
            f"Select a channel to view plans:"
        )
        
        await message.answer(
            welcome_message,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
            parse_mode="HTML"
        )