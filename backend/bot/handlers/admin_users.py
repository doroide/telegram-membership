from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from backend.app.db.session import async_session
from backend.app.db.models import User
from datetime import datetime

router = Router()

ADMIN_ID = 5793624035 # <-- CHANGE THIS TO YOUR TELEGRAM ID


@router.message(Command("users"))
async def list_users(message: Message):

    if message.from_user.id != ADMIN_ID:
        return await message.answer("❌ Not authorized.")

    async with async_session() as session:
        result = await session.execute(User.select())
        users = result.scalars().all()

        if not users:
            return await message.answer("📭 No users found in database.")

        active = [u for u in users if u.status == "active"]
        inactive = [u for u in users if u.status == "inactive"]

        text = (
            "👥 <b>User Summary</b>\n\n"
            f"🟢 Active Users: {len(active)}\n"
            f"🔴 Inactive Users: {len(inactive)}\n"
            f"📦 Total Users: {len(users)}\n\n"
            "======================\n"
            "<b>User Details:</b>\n"
        )

        for user in users:
            exp = user.expiry_date.strftime('%d-%m-%Y') if user.expiry_date else "N/A"
            text += (
                f"\n👤 <b>{user.telegram_username or 'No Username'}</b>\n"
                f"ID: <code>{user.telegram_id}</code>\n"
                f"Plan: {user.plan_id}\n"
                f"Status: {user.status.upper()}\n"
                f"Expiry: {exp}\n"
                f"Failed Attempts: {user.attempts_failed}\n"
                "-----------------------------"
            )

        await message.answer(text, disable_web_page_preview=True)
