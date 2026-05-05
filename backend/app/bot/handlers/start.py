import os
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, BotCommand, BotCommandScopeChat
from aiogram.filters import Command
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.app.db.session import async_session
from backend.app.db.models import User, Channel, Membership

router = Router()

# Admin contact username
ADMIN_USERNAME = "Doroide47"

# Admin IDs — env var + hardcoded
ADMIN_IDS = [5793624035, 952763698] + [
    int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()
]


# =====================================================
# REGISTER BOT MENU COMMANDS
# =====================================================

USER_COMMANDS = [
    BotCommand(command="start",      description="🏠 Main Menu"),
    BotCommand(command="membership", description="🚀 Browse Channels & Plans"),
    BotCommand(command="myplans",    description="📋 My Subscriptions"),
    BotCommand(command="offers",     description="🎁 Special Offers"),
    BotCommand(command="help",       description="💬 Support & Contact"),
]

ADMIN_COMMANDS = [
    BotCommand(command="admin",      description="🛠 Admin Panel"),
    BotCommand(command="adduser",    description="➕ Add User Manually"),
    BotCommand(command="addchannel", description="📺 Add New Channel"),
    BotCommand(command="sendlinks",  description="🔗 Send Access Links"),
    BotCommand(command="userinfo",   description="👤 User Info"),
    BotCommand(command="broadcast",  description="📢 Broadcast Message"),
    BotCommand(command="kick",       description="🦵 Kick User"),
    BotCommand(command="dailyreport", description="👥 Daily Member Report"),
    BotCommand(command="members", description="👥 Members Panel"),
]


async def set_bot_commands(bot):
    """Called on startup — sets default user commands globally."""
    await bot.set_my_commands(USER_COMMANDS)


async def set_commands_for_user(bot, telegram_id: int):
    """Called on /start — sets scoped commands based on admin or user."""
    scope = BotCommandScopeChat(chat_id=telegram_id)
    if telegram_id in ADMIN_IDS:
        await bot.set_my_commands(ADMIN_COMMANDS, scope=scope)
    else:
        await bot.set_my_commands(USER_COMMANDS, scope=scope)


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

        # ── Set scoped menu commands for this user ──────────────
        try:
            from backend.bot.bot import bot
            await set_commands_for_user(bot, telegram_id)
        except Exception as e:
            print(f"[START] Could not set commands: {e}")

        if not has_active and telegram_id not in ADMIN_IDS:
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
# /MEMBERSHIP COMMAND
# =====================================================

@router.message(Command("membership"))
async def membership_command(message: Message):
    from backend.app.bot.handlers.channel_plans import send_channel_list
    await send_channel_list(message, message.from_user.id, edit=False)


# =====================================================
# /OFFERS COMMAND
# =====================================================

@router.message(Command("offers"))
async def offers_command(message: Message):
    from backend.app.db.models import UpsellAttempt
    from sqlalchemy import and_

    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        user = result.scalar_one_or_none()

        if not user:
            await message.answer("❌ User not found. Please send /start first.")
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
            await message.answer(
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

        keyboard_buttons.append([
            InlineKeyboardButton(text="🏠 Back to Home", callback_data="menu_back_home")
        ])

        await message.answer(
            msg,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        )


# =====================================================
# /HELP COMMAND
# =====================================================

@router.message(Command("help"))
async def help_command(message: Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Contact Admin", url=f"https://t.me/{ADMIN_USERNAME}")],
        [InlineKeyboardButton(text="🏠 Back to Home", callback_data="menu_back_home")],
    ])
    await message.answer(
        "💬 <b>Support & Contact</b>\n\n"
        "Having trouble? We're here to help!\n\n"
        "📩 Reach out to our admin directly:\n"
        f"👤 @{ADMIN_USERNAME}\n\n"
        "⚡ We typically respond within a few minutes.",
        parse_mode="HTML",
        reply_markup=keyboard
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