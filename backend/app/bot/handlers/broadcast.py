import os
import asyncio
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select

from backend.app.db.session import async_session
from backend.app.db.models import User, Membership, Channel
from backend.bot.bot import bot

router = Router()

ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x]


class BroadcastStates(StatesGroup):
    selecting_audience = State()
    waiting_user_ids = State()
    selecting_channel = State()
    waiting_message = State()
    confirming = State()


# =====================================================
# STEP 1: Admin clicks Broadcast in admin panel
# =====================================================

@router.callback_query(F.data == "admin_broadcast")
async def broadcast_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Not authorized", show_alert=True)
        return

    await state.set_state(BroadcastStates.selecting_audience)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 All Users", callback_data="bc_audience_all")],
        [InlineKeyboardButton(text="🎯 Specific Users", callback_data="bc_audience_specific")],
        [InlineKeyboardButton(text="📺 By Channel", callback_data="bc_audience_channel")],
        [InlineKeyboardButton(text="❌ Cancel", callback_data="admin_back_main")]
    ])

    await callback.message.edit_text(
        "📢 <b>Broadcast Message</b>\n\n"
        "Who do you want to send to?",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback.answer()


# =====================================================
# STEP 2A: All Users selected
# =====================================================

@router.callback_query(F.data == "bc_audience_all")
async def bc_audience_all(callback: CallbackQuery, state: FSMContext):
    await state.update_data(audience="all", target_ids=None)
    await state.set_state(BroadcastStates.waiting_message)

    await callback.message.edit_text(
        "📢 <b>Broadcast to All Users</b>\n\n"
        "Send your message now.\n"
        "Supports text, images, links, and emojis.\n\n"
        "Just send it as a normal message 👇",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Cancel", callback_data="admin_back_main")]
        ]),
        parse_mode="HTML"
    )
    await callback.answer()


# =====================================================
# STEP 2B: Specific Users selected
# =====================================================

@router.callback_query(F.data == "bc_audience_specific")
async def bc_audience_specific(callback: CallbackQuery, state: FSMContext):
    await state.set_state(BroadcastStates.waiting_user_ids)

    await callback.message.edit_text(
        "📢 <b>Broadcast to Specific Users</b>\n\n"
        "Enter Telegram IDs separated by commas:\n"
        "<code>123456789, 987654321, 111222333</code>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Cancel", callback_data="admin_back_main")]
        ]),
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(BroadcastStates.waiting_user_ids)
async def bc_receive_user_ids(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return

    try:
        ids = [int(x.strip()) for x in message.text.split(",") if x.strip()]
        if not ids:
            raise ValueError
    except ValueError:
        await message.answer("❌ Invalid format. Enter comma-separated numeric IDs.")
        return

    await state.update_data(audience="specific", target_ids=ids)
    await state.set_state(BroadcastStates.waiting_message)

    await message.answer(
        f"✅ <b>{len(ids)} user(s) selected</b>\n\n"
        "Now send your message.\n"
        "Supports text, images, links, and emojis 👇",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Cancel", callback_data="admin_back_main")]
        ]),
        parse_mode="HTML"
    )


# =====================================================
# STEP 2C: By Channel selected — show channel list
# =====================================================

@router.callback_query(F.data == "bc_audience_channel")
async def bc_audience_channel(callback: CallbackQuery, state: FSMContext):
    async with async_session() as session:
        result = await session.execute(select(Channel).where(Channel.is_active == True))
        channels = result.scalars().all()

    if not channels:
        await callback.message.edit_text(
            "❌ No active channels found.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Back", callback_data="admin_back_main")]
            ])
        )
        await callback.answer()
        return

    buttons = [
        [InlineKeyboardButton(text=f"📺 {c.name}", callback_data=f"bc_channel_{c.id}")]
        for c in channels
    ]
    buttons.append([InlineKeyboardButton(text="❌ Cancel", callback_data="admin_back_main")])

    await state.set_state(BroadcastStates.selecting_channel)
    await callback.message.edit_text(
        "📺 <b>Select Channel</b>\n\nWhich channel's members to message?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("bc_channel_"))
async def bc_channel_selected(callback: CallbackQuery, state: FSMContext):
    channel_id = int(callback.data.split("_")[2])

    async with async_session() as session:
        channel = await session.get(Channel, channel_id)
        result = await session.execute(
            select(User.telegram_id)
            .join(Membership, Membership.user_id == User.id)
            .where(
                Membership.channel_id == channel_id,
                Membership.is_active == True
            )
        )
        ids = [r[0] for r in result.fetchall()]

    await state.update_data(audience="channel", target_ids=ids, channel_name=channel.name)
    await state.set_state(BroadcastStates.waiting_message)

    await callback.message.edit_text(
        f"✅ <b>{len(ids)} active member(s)</b> in {channel.name}\n\n"
        "Now send your message.\n"
        "Supports text, images, links, and emojis 👇",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Cancel", callback_data="admin_back_main")]
        ]),
        parse_mode="HTML"
    )
    await callback.answer()


# =====================================================
# STEP 3: Receive message — show confirmation
# =====================================================

@router.message(BroadcastStates.waiting_message)
async def bc_receive_message(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return

    data = await state.get_data()
    audience = data.get("audience")
    target_ids = data.get("target_ids")

    # Store message info
    await state.update_data(
        msg_id=message.message_id,
        chat_id=message.chat.id,
        has_photo=bool(message.photo),
        caption=message.caption,
        text=message.text,
        photo_id=message.photo[-1].file_id if message.photo else None
    )
    await state.set_state(BroadcastStates.confirming)

    # Audience label
    if audience == "all":
        async with async_session() as session:
            result = await session.execute(select(User.telegram_id))
            count = len(result.fetchall())
        audience_label = f"👥 All Users ({count} total)"
    elif audience == "specific":
        audience_label = f"🎯 Specific Users ({len(target_ids)} selected)"
    else:
        channel_name = data.get("channel_name", "channel")
        audience_label = f"📺 {channel_name} members ({len(target_ids)} active)"

    await message.answer(
        f"📋 <b>Confirm Broadcast</b>\n\n"
        f"📤 Send to: {audience_label}\n\n"
        f"Are you sure you want to send this message?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Yes, Send", callback_data="bc_confirm_send"),
                InlineKeyboardButton(text="❌ Cancel", callback_data="admin_back_main")
            ]
        ]),
        parse_mode="HTML"
    )


# =====================================================
# STEP 4: Confirmed — send to all targets
# =====================================================

@router.callback_query(F.data == "bc_confirm_send")
async def bc_confirm_send(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Not authorized", show_alert=True)
        return

    data = await state.get_data()
    audience = data.get("audience")
    target_ids = data.get("target_ids")
    has_photo = data.get("has_photo")
    photo_id = data.get("photo_id")
    caption = data.get("caption")
    text = data.get("text")

    await state.clear()

    # Get all user IDs if audience is all
    if audience == "all":
        async with async_session() as session:
            result = await session.execute(select(User.telegram_id))
            target_ids = [r[0] for r in result.fetchall()]

    await callback.message.edit_text("📤 Sending... please wait.")

    sent = 0
    failed = 0

    for tg_id in target_ids:
        try:
            if has_photo and photo_id:
                await bot.send_photo(
                    chat_id=tg_id,
                    photo=photo_id,
                    caption=caption or "",
                    parse_mode="HTML"
                )
            else:
                await bot.send_message(
                    chat_id=tg_id,
                    text=text or "",
                    parse_mode="HTML"
                )
            sent += 1
            await asyncio.sleep(0.05)  # Prevent spam detection
        except Exception:
            failed += 1

    await callback.message.edit_text(
        f"✅ <b>Broadcast Complete</b>\n\n"
        f"📤 Sent: {sent}\n"
        f"❌ Failed: {failed}\n"
        f"📊 Total: {sent + failed}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Back to Admin Panel", callback_data="admin_back_main")]
        ]),
        parse_mode="HTML"
    )
    await callback.answer()


# =====================================================
# LEGACY COMMANDS (kept for backward compatibility)
# =====================================================

@router.message(Command("broadcast"))
async def broadcast_all(message: Message, command: CommandObject):
    if message.from_user.id not in ADMIN_IDS:
        return
    if not command.args:
        await message.answer("Usage:\n/broadcast your message here")
        return
    text = command.args
    async with async_session() as session:
        result = await session.execute(select(User.telegram_id))
        users = [r[0] for r in result.fetchall()]
    sent = 0
    for tg_id in users:
        try:
            await message.bot.send_message(tg_id, text)
            sent += 1
        except:
            pass
    await message.answer(f"✅ Sent to {sent} users")


@router.message(Command("broadcast_channel"))
async def broadcast_channel(message: Message, command: CommandObject):
    if message.from_user.id not in ADMIN_IDS:
        return
    if not command.args:
        await message.answer("Usage:\n/broadcast_channel <channel_id> message")
        return
    parts = command.args.split(" ", 1)
    if len(parts) < 2:
        await message.answer("Provide channel id + message")
        return
    channel_id = int(parts[0])
    text = parts[1]
    async with async_session() as session:
        result = await session.execute(
            select(User.telegram_id)
            .join(Membership, Membership.user_id == User.id)
            .where(Membership.channel_id == channel_id, Membership.is_active == True)
        )
        users = [r[0] for r in result.fetchall()]
    sent = 0
    for tg_id in users:
        try:
            await message.bot.send_message(tg_id, text)
            sent += 1
        except:
            pass
    await message.answer(f"✅ Sent to {sent} users of channel {channel_id}")