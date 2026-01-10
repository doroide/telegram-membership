from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from sqlalchemy import select
from backend.app.db.session import async_session
from backend.app.db.models import User

admin_router = Router()


@admin_router.message(Command("find"))
async def find_user(message: Message):
    # Ensure admin sent an ID
    args = message.text.split()
    if len(args) < 2:
        return await message.answer("Usage: /find <telegram_id>")

    telegram_id = args[1].strip()

    # Query database
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar()

    if not user:
        return await message.answer("❌ User not found")

    # Format user details
    status = "ACTIVE ✅" if user.is_active else "EXPIRED ❌"
    expiry = user.expiry_date.strftime("%Y-%m-%d") if user.expiry_date else "N/A"

    reply = (
        f"📌 *User Details Found*\n\n"
        f"*Telegram ID:* `{user.telegram_id}`\n"
        f"*Username:* @{user.username}\n"
        f"*Plan:* {user.plan}\n"
        f"*Expiry:* {expiry}\n"
        f"*Status:* {status}"
    )

    await message.answer(reply, parse_mode="Markdown")
