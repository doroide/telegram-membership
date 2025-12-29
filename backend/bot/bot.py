import os
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from backend.app.config.plans import PLANS


BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN is missing")

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher()

@dp.message(commands=["start"])
async def start(message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=PLANS["plan_199_4m"]["label"], callback_data="plan_199_4m")],
        [InlineKeyboardButton(text=PLANS["plan_399_3m"]["label"], callback_data="plan_399_3m")],
        [InlineKeyboardButton(text=PLANS["plan_599_6m"]["label"], callback_data="plan_599_6m")],
        [InlineKeyboardButton(text=PLANS["plan_799_12m"]["label"], callback_data="plan_799_12m")],
    ])

    await message.answer(
        "🎬 *Movies Premium Doroide*\n\n"
        "Choose a subscription plan 👇",
        reply_markup=keyboard
    )
from backend.app.services.payment_service import create_order
@dp.callback_query(lambda c: c.data in PLANS.keys())
async def handle_plan_selection(callback):
    plan_id = callback.data
    plan = PLANS[plan_id]

    order = create_order(
        amount_in_rupees=plan["price"],
        user_id=callback.from_user.id,
        plan_id=plan_id
    )

    payment_link = f"https://rzp.io/i/{order['id']}"

    await callback.message.answer(
        f"✅ *Plan Selected*\n\n"
        f"📦 {plan['label']}\n"
        f"🔗 Pay here:\n{payment_link}"
    )

    await callback.answer()



async def start_bot():
    print("Bot polling started")
    await dp.start_polling(bot)
