import asyncio
from aiogram import Router
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.enums import ContentType

from backend.app.db.session import async_session
from backend.app.db.models import User
from backend.bot.bot import bot

router = Router()

ADMIN_ID = 5793624035


# ================================
# 1️⃣ STANDARD BROADCAST
# ================================
@router.message(Command("broadcast"))
async def broadcast_start(message: Message):
    if message.from_user.id != ADMIN_ID:
        return await message.answer("❌ Unauthorized")

    await message.answer(
        "📢 <b>Broadcast mode ON</b>\n"
        "Send the message/media you want to broadcast.",
        parse_mode="HTML"
    )


@router.message()
async def broadcast_message(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    await execute_broadcast(message)


async def execute_broadcast(message: Message, plan_filter=None, buttons=None):
    content_type = message.content_type

    async with async_session() as session:
        if plan_filter:
            result = await session.execute(
                User.select().where(User.plan_id == plan_filter, User.status == "active")
            )
        else:
            result = await session.execute(
                User.select().where(User.status == "active")
            )

        users = result.scalars().all()

    sent = 0
    failed = 0

    for user in users:
        try:
            if content_type == ContentType.PHOTO:
                await bot.send_photo(
                    chat_id=user.telegram_id,
                    photo=message.photo[-1].file_id,
                    caption=message.caption or "",
                    reply_markup=buttons
                )
            elif content_type == ContentType.VIDEO:
                await bot.send_video(
                    chat_id=user.telegram_id,
                    video=message.video.file_id,
                    caption=message.caption or "",
                    reply_markup=buttons
                )
            elif content_type == ContentType.DOCUMENT:
                await bot.send_document(
                    chat_id=user.telegram_id,
                    document=message.document.file_id,
                    caption=message.caption or "",
                    reply_markup=buttons
                )
            else:
                await bot.send_message(
                    chat_id=user.telegram_id,
                    text=message.text,
                    reply_markup=buttons
                )

            sent += 1
        except:
            failed += 1

        await asyncio.sleep(0.05)

    await message.answer(
        f"📢 <b>Broadcast Complete</b>\n"
        f"🟢 Sent: {sent}\n"
        f"🔴 Failed: {failed}",
        parse_mode="HTML"
    )


# ================================
# 2️⃣ BROADCAST TO SPECIFIC PLAN
# ================================
@router.message(Command("broadcast_plan"))
async def broadcast_plan(message: Message):
    if message.from_user.id != ADMIN_ID:
        return await message.answer("❌ Unauthorized")

    parts = message.text.split()

    if len(parts) != 2:
        return await message.answer(
            "Usage:\n\n/broadcast_plan plan_199_4m"
        )

    plan_id = parts[1]

    message.ctx_plan_id = plan_id

    await message.answer(
        f"📦 Broadcasting to users of plan: <b>{plan_id}</b>\n\n"
        "Now send the message/media to broadcast.",
        parse_mode="HTML"
    )


# ================================
# 3️⃣ BROADCAST WITH BUTTONS
# ================================
@router.message(Command("broadcast_buttons"))
async def broadcast_buttons_start(message: Message):
    if message.from_user.id != ADMIN_ID:
        return await message.answer("❌ Unauthorized")

    message.bot_state = "await_message"
    await message.answer("📨 Send the message you want to broadcast with a button.")


@router.message()
async def broadcast_buttons_handler(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    if getattr(message, "bot_state", None) == "await_message":
        message.bot_message_to_send = message
        message.bot_state = "await_button"
        return await message.answer(
            "🔘 Now send button text & URL like this:\n\n"
            "`Watch Now - https://example.com`",
            parse_mode="Markdown"
        )

    if getattr(message, "bot_state", None) == "await_button":
        try:
            text, url = message.text.split(" - ")
        except:
            return await message.answer("❌ Incorrect format. Use:\nText - URL")

        button = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text=text, url=url)]]
        )

        await execute_broadcast(
            message.bot_message_to_send,
            buttons=button
        )

        return await message.answer("🎉 Broadcast with button sent!")


# ================================
# 4️⃣ DAILY SCHEDULED BROADCAST
# ================================
daily_message = None
daily_enabled = False


@router.message(Command("set_daily_broadcast"))
async def set_daily_broadcast(message: Message):
    global daily_message, daily_enabled

    if message.from_user.id != ADMIN_ID:
        return await message.answer("❌ Unauthorized")

    daily_message = message.text.replace("/set_daily_broadcast", "").strip()
    daily_enabled = True

    await message.answer("⏰ Daily broadcast message saved & enabled!")


@router.message(Command("disable_daily_broadcast"))
async def disable_daily(message: Message):
    global daily_enabled

    if message.from_user.id != ADMIN_ID:
        return await message.answer("❌ Unauthorized")

    daily_enabled = False
    await message.answer("❌ Daily broadcast disabled")


async def daily_broadcast_scheduler():
    global daily_enabled, daily_message

    while True:
        if daily_enabled and daily_message:
            fake_msg = Message(text=daily_message)
            await execute_broadcast(fake_msg)

        await asyncio.sleep(24 * 60 * 60)  # run every 24 hours
