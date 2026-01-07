from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from datetime import datetime
from backend.app.db.session import async_session
from backend.app.db.models import User

router = Router()

ADMIN_ID = 123456789   # CHANGE TO YOUR TELEGRAM USER ID


@router.message(Command("expired_users"))
async def expired_users(message: Message):

    if message.from_user.id != ADMIN_ID:
        return await message.answer("❌ You are not authorized.")

    await message.answer("🔍 Checking expired users...")

    async with async_session() as session:
        result = await session.execute(
            User.select().where(User.status == "inactive")
        )
        users = result.scalars().all()

    if not users:
        return await message.answer("✅ No expired users found.")

    text = "❌ <b>Expired Users List</b>\n\n"

    for user in users:
        expiry = user.expiry_date.strftime("%d-%m-%Y") if user.expiry_date else "N/A"
        text += (
            f"👤 <b>{user.telegram_id}</b>\n"
            f"📛 Username: @{user.telegram_username or 'N/A'}\n"
            f"📅 Expired: {expiry}\n"
            f"📦 Plan: {user.plan_id}\n"
            f"— — — — — — — — — — — —\n"
        )

    # Split into multiple messages if too long
    for chunk in split_message(text):
        await message.answer(chunk, parse_mode="HTML")


def split_message(text, limit=3800):
    parts = []
    while len(text) > limit:
        part = text[:limit]
        parts.append(part)
        text = text[limit:]
    parts.append(text)
    return parts
