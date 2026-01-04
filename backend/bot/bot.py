import os
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command

from backend.app.config.plans import PLANS
from backend.app.services.payment_service import create_payment_link

# ========================
# BOT INITIALIZATION
# ========================

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN is missing")

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher()

# ========================
# /start COMMAND
# ========================

@dp.message(Command("start"))
async def start(message):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=PLANS["plan_199_4m"]["label"], callback_data="plan_199_4m")],
            [InlineKeyboardButton(text=PLANS["plan_399_3m"]["label"], callback_data="plan_399_3m")],
            [InlineKeyboardButton(text=PLANS["plan_599_6m"]["label"], callback_data="plan_599_6m")],
            [InlineKeyboardButton(text=PLANS["plan_799_12m"]["label"], callback_data="plan_799_12m")],
        ]
    )

    await message.answer(
        "🎬 <b>Movies Premium Doroide</b>\n\n"
        "Choose a subscription plan 👇",
        reply_markup=keyboard
    )

# ========================
# PLAN SELECTION HANDLER
# ========================

@dp.callback_query(lambda c: c.data in PLANS.keys())
async def handle_plan_selection(callback):
    plan_id = callback.data
    plan = PLANS[plan_id]

    payment = create_payment_link(
        amount_in_rupees=plan["price"],
        user_id=callback.from_user.id,
        plan_id=plan_id
    )

    await callback.message.answer(
        f"✅ <b>Plan Selected</b>\n\n"
        f"📦 {plan['label']}\n"
        f"🔗 <b>Pay here:</b>\n{payment['short_url']}\n\n"
        f"⚠️ After payment, you will automatically receive the channel invite."
    )

    await callback.answer()

# ========================
# BOT START FUNCTION
# ========================

async def set_webhook(webhook_url: str):
    await bot.set_webhook(webhook_url)
