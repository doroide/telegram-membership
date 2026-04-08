import os
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
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
    telegram_id = message.from_user.id

    async with async_session() as session:
        # Get or create user
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()

        if not user:
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

        # Check if user has any active memberships
        active_check = await session.execute(
            select(Membership).where(
                Membership.user_id == user.id,
                Membership.is_active == True
            )
        )
        has_active = active_check.scalars().first()

        if not has_active:
            try:
                await message.answer(
                    "⏳ *Your Access is Being Activated*\n\n"
                    "We are currently setting up your premium membership 🔐\n"
                    "⚡ This usually takes a short time.\n\n"
                    "📩 You will receive your access link here once it's ready.\n\n"
                    "🔥 Welcome to Doroide Premium",
                    parse_mode="Markdown"
                )
            except Exception as e:
                print(f"[START] Could not send activation message: {e}")
            return

    # Build main menu keyboard
    keyboard = [
        [InlineKeyboardButton(text="🚀 Membership", callback_data="menu_membership")],
        [InlineKeyboardButton(text="📋 My Plans", callback_data="my_plans")],
        [InlineKeyboardButton(text="🎁 Offers for You", callback_data="view_all_upsells")],
        [InlineKeyboardButton(text="📞 Contact Admin", url=f"https://t.me/{ADMIN_USERNAME}")],
    ]

    welcome_message = (
        f"👋 <b>Welcome, {message.from_user.first_name}!</b>\n\n"
        f"Get instant access to our <b>premium membership</b>.\n\n"
        f"<b>Steps to get membership:</b>\n"
        f"1️⃣ Tap <b>Membership</b>\n"
        f"2️⃣ Select a Channel\n"
        f"3️⃣ Choose a Plan\n"
        f"4️⃣ Complete Payment\n\n"
        f"✅ Access is granted automatically after payment."
    )

    await message.answer(
        welcome_message,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
        parse_mode="HTML"
    )


# =====================================================
# MEMBERSHIP BUTTON → SHOW CHANNEL LIST
# =====================================================

@router.callback_query(F.data == "menu_membership")
async def on_menu_membership(callback: CallbackQuery):
    from backend.app.bot.handlers.channel_plans import send_channel_list
    try:
        await callback.answer()
    except Exception:
        pass
    await send_channel_list(callback.message, callback.from_user.id, edit=True)


# =====================================================
# BACK TO HOME
# =====================================================

@router.callback_query(F.data == "menu_back_home")
async def on_back_home(callback: CallbackQuery):
    first_name = callback.from_user.first_name or "there"
    keyboard = [
        [InlineKeyboardButton(text="🚀 Membership", callback_data="menu_membership")],
        [InlineKeyboardButton(text="📋 My Plans", callback_data="my_plans")],
        [InlineKeyboardButton(text="🎁 Offers for You", callback_data="view_all_upsells")],
        [InlineKeyboardButton(text="📞 Contact Admin", url=f"https://t.me/{ADMIN_USERNAME}")],
    ]
    text = (
        f"👋 <b>Welcome, {first_name}!</b>\n\n"
        f"Get instant access to our <b>premium membership</b>.\n\n"
        f"<b>Steps to get membership:</b>\n"
        f"1️⃣ Tap <b>Membership</b>\n"
        f"2️⃣ Select a Channel\n"
        f"3️⃣ Choose a Plan\n"
        f"4️⃣ Complete Payment\n\n"
        f"✅ Access is granted automatically after payment."
    )
    try:
        await callback.answer()
    except Exception:
        pass
    try:
        await callback.message.edit_text(
            text, parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
        )
    except Exception:
        await callback.message.answer(
            text, parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
        )