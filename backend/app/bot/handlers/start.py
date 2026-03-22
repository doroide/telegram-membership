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

        # Check if user has any active memberships
        active_check = await session.execute(
            select(Membership).where(
                Membership.user_id == user.id,
                Membership.is_active == True
            )
        )
        has_active = active_check.scalar_one_or_none()

        if not has_active:
            await message.answer(
                "⏳ *Your Access is Being Activated*\n\n"
                "We are currently setting up your premium membership 🔐\n"
                "⚡ This usually takes a short time.\n\n"
                "📩 You will receive your access link here once it's ready.\n\n"
                "🔥 Welcome to Doroide Premium",
                parse_mode="Markdown"
            )
            return
        
        # Build channel selection keyboard
       # Fixed channel emojis by channel ID
        channel_emojis = {
            12: "📺", 13: "🔥", 14: "🎬", 15: "📚",
            16: "🔞", 17: "💫", 18: "💎", 19: "🎭",
            20: "📸", 21: "🌶️"
        }

        # Build channel selection keyboard
        keyboard = []
        for idx, channel in enumerate(channels, 1):
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

            ch_emoji = channel_emojis.get(channel.id, "📺")

            keyboard.append([
                InlineKeyboardButton(
                   text=f"{idx}. {ch_emoji} {channel.name}",
                    callback_data=f"userch_{channel.id}"
                )
            ])
        
        # Add My Plans and Contact Admin buttons
        keyboard.append([
            InlineKeyboardButton(text="📋 My Plans", callback_data="my_plans")
        ])

        keyboard.append([
            InlineKeyboardButton(text="🎁 Offers for You", callback_data="view_all_upsells")
        ])
        keyboard.append([
            InlineKeyboardButton(text="📞 Contact Admin", url=f"https://t.me/{ADMIN_USERNAME}")
        ])
        
        welcome_message = (
            f"👋 <b>Welcome, {message.from_user.first_name}!</b>\n\n"
            f"🎬 <b>Premium Content Collections</b>\n"
            f"Choose a channel below to view plans and get instant access.\n\n"
            f"⚡ Direct Videos\n"
            f"⚡ HD Quality\n"
            f"⚡ Daily Updates\n\n"
            f"👇 Select a channel to get started:"
        )
        
        await message.answer(
            welcome_message,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
            parse_mode="HTML"
        )