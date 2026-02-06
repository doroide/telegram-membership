import os
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode


# ======================================================
# TELEGRAM BOT CORE (ONLY INITIALIZATION HERE)
# ======================================================

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not BOT_TOKEN:
    raise RuntimeError("❌ TELEGRAM_BOT_TOKEN missing")


# Create bot instance
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)


# Create dispatcher
dp = Dispatcher()


print("🤖 Bot core initialized")
