from aiogram import Router, F
from aiogram.types import Message

from backend.app.db.session import async_session
from backend.app.services.stats_service import StatsService
from backend.bot.utils.admin import is_admin

router = Router()


@router.message(F.text == "/stats")
async def stats(message: Message):

    if not is_admin(message.from_user.id):
        return

    async with async_session() as session:
        today = await StatsService.today_revenue(session)
        month = await StatsService.monthly_revenue(session)
        active = await StatsService.active_users(session)
        expired = await StatsService.expired_users(session)

    await message.answer(
        f"📊 Stats\n\n"
        f"Today Revenue: ₹{today}\n"
        f"Monthly Revenue: ₹{month}\n"
        f"Active Memberships: {active}\n"
        f"Expired: {expired}"
    )
