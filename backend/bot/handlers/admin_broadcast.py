import asyncio
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from backend.app.db.session import async_session
from backend.app.db.models import User

router = Router()

ADMIN_ID = 5793624035  # YOUR ADMIN ID


@router.message(Command("broadcast"))
async def broadcast(message: Message):
    # Import bot INSIDE to avoid circular import
    from backend.bot.bot import bot

    if message.from_user.id != ADMIN_ID:
        return await message.answer("❌ You are not authorized.")

    text = message.text.replace("/broadcast", "").strip()

    if not text:
        return await message.answer(
            "📢 <b>Broadcast Usage:</b>\n\n"
            "`/broadcast Your message here...`",
            parse_mode="HTML"
        )

    await message.answer("📡 Sending broadcast to all active users…")

    async with async_session() as session:
        result = await session.execute(User.select().where(User.status == "active"))
        users = result.scalars().all()

    success = 0
    failed = 0

    for user in users:
        try:
            await bot.send_message(user.telegram_id, text)
            success += 1
        except Exception:
            failed += 1

        await asyncio.sleep(0.05)

    await message.answer(
        f"📤 <b>Broadcast Completed</b>\n"
        f"🟢 Delivered: {success}\n"
        f"🔴 Failed: {failed}",
        parse_mode="HTML"
    )
