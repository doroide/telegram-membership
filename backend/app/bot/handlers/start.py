from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command

router = Router()


# =====================================================
# /start
# =====================================================
@router.message(Command("start"))
async def start_handler(message: Message):
    await message.answer(
        "👋 Welcome!\n\n"
        "Use:\n"
        "/myplans – View your plans\n"
        "/renew – Renew membership\n"
    )
