import os
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select, and_

from backend.app.db.session import async_session
from backend.app.db.models import User, Membership, Channel
from backend.bot.bot import bot

router = Router()

ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x]


class KickUserStates(StatesGroup):
    waiting_for_user_id = State()


# =====================================================
# STEP 1: Admin clicks Kick User
# =====================================================

@router.callback_query(F.data == "admin_kick_user")
async def kick_user_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Not authorized", show_alert=True)
        return

    await state.set_state(KickUserStates.waiting_for_user_id)

    await callback.message.edit_text(
        "🦵 <b>Kick User</b>\n\n"
        "Enter the Telegram ID of the user you want to kick:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Cancel", callback_data="admin_back_main")]
        ]),
        parse_mode="HTML"
    )
    await callback.answer()


# =====================================================
# STEP 2: Admin enters Telegram ID — show their channels
# =====================================================

@router.message(KickUserStates.waiting_for_user_id)
async def kick_user_show_channels(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return

    try:
        telegram_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Invalid ID. Please enter a valid numeric Telegram ID.")
        return

    async with async_session() as session:
        user = await session.scalar(
            select(User).where(User.telegram_id == telegram_id)
        )

        if not user:
            await message.answer(
                "❌ User not found in database.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 Back", callback_data="admin_back_main")]
                ])
            )
            await state.clear()
            return

        # Get active memberships
        result = await session.execute(
            select(Membership, Channel)
            .join(Channel, Membership.channel_id == Channel.id)
            .where(
                and_(
                    Membership.user_id == user.id,
                    Membership.is_active == True
                )
            )
        )
        active = result.all()

    if not active:
        await message.answer(
            f"ℹ️ User <code>{telegram_id}</code> has no active memberships.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Back", callback_data="admin_back_main")]
            ]),
            parse_mode="HTML"
        )
        await state.clear()
        return

    # Show channels as buttons
    buttons = [
        [InlineKeyboardButton(
            text=f"📺 {channel.name}",
            callback_data=f"kick_confirm_{user.id}_{telegram_id}_{membership.id}_{channel.id}"
        )]
        for membership, channel in active
    ]
    buttons.append([InlineKeyboardButton(text="❌ Cancel", callback_data="admin_back_main")])

    await message.answer(
        f"👤 User: <b>{user.full_name or user.username or telegram_id}</b>\n"
        f"🆔 Telegram ID: <code>{telegram_id}</code>\n\n"
        f"Select the channel to kick them from:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML"
    )
    await state.clear()


# =====================================================
# STEP 3: Admin clicks channel — kick the user
# =====================================================

@router.callback_query(F.data.startswith("kick_confirm_"))
async def kick_user_execute(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Not authorized", show_alert=True)
        return

    parts = callback.data.split("_")
    # kick_confirm_{user_id}_{telegram_id}_{membership_id}_{channel_id}
    user_id = int(parts[2])
    telegram_id = int(parts[3])
    membership_id = int(parts[4])
    channel_id = int(parts[5])

    async with async_session() as session:
        membership = await session.get(Membership, membership_id)
        channel = await session.get(Channel, channel_id)

        if not membership or not channel:
            await callback.answer("❌ Data not found", show_alert=True)
            return

        # Deactivate membership
        membership.is_active = False
        await session.commit()

    # Kick from Telegram channel
    try:
        await bot.ban_chat_member(
            chat_id=int(channel.telegram_chat_id),
            user_id=telegram_id
        )
        await bot.unban_chat_member(
            chat_id=int(channel.telegram_chat_id),
            user_id=telegram_id
        )
    except Exception as e:
        await callback.message.edit_text(
            f"⚠️ Membership deactivated but failed to kick from Telegram:\n<code>{e}</code>",
            parse_mode="HTML"
        )
        await callback.answer()
        return

    # Notify user
    try:
        await bot.send_message(
            chat_id=telegram_id,
            text=(
                f"⛔ <b>Access Removed</b>\n\n"
                f"You have been removed from <b>{channel.name}</b> by an admin.\n\n"
                f"If you think this is a mistake, please contact admin @Doroide47."
            ),
            parse_mode="HTML"
        )
    except Exception:
        pass  # User may have blocked the bot

    await callback.message.edit_text(
        f"✅ <b>User Kicked Successfully</b>\n\n"
        f"👤 Telegram ID: <code>{telegram_id}</code>\n"
        f"📺 Channel: <b>{channel.name}</b>\n"
        f"🔴 Membership deactivated\n"
        f"📩 User notified",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Back to Admin Panel", callback_data="admin_back_main")]
        ]),
        parse_mode="HTML"
    )
    await callback.answer()