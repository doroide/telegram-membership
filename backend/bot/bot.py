import logging
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery
)

from backend.app.config import settings
from backend.app.services.razorpay_client import client

logging.basicConfig(level=logging.INFO)

# =========================
# BOT SETUP
# =========================
bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

# =========================
# /start
# =========================
@dp.message(Command("start"))
async def start_handler(message: Message):
    await message.answer(
        "👋 Welcome!\n\n"
        "This is your Telegram Membership Bot.\n"
        "Use /plans to see available subscriptions."
    )

# =========================
# /plans
# =========================
@dp.message(Command("plans"))
async def plans_handler(message: Message):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="₹99 / Month", callback_data="plan_99")],
            [InlineKeyboardButton(text="₹199 / Month", callback_data="plan_199")]
        ]
    )

    await message.answer(
        "💳 Choose your subscription plan:",
        reply_markup=keyboard
    )

# =========================
# CREATE PAYMENT LINK
# =========================
async def create_payment_link_and_send(
    callback: CallbackQuery,
    amount: int,
    plan_name: str
):
    payment_link = client.payment_link.create({
        "amount": amount * 100,  # paise
        "currency": "INR",
        "accept_partial": False,
        "description": plan_name,
        "customer": {
    "name": callback.from_user.full_name or "Telegram User"
},

        "notify": {
            "sms": False,
            "email": False
        },
        "notes": {
            "telegram_id": str(callback.from_user.id),
            "plan": plan_name
        }
    })

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💳 Pay Now", url=payment_link["short_url"])]
        ]
    )

    await callback.message.answer(
        f"💰 *{plan_name}*\n\nClick below to complete payment:",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    await callback.answer()

# =========================
# ₹99 PLAN
# =========================
@dp.callback_query(F.data == "plan_99")
async def plan_99_callback(callback: CallbackQuery):
    await create_payment_link_and_send(
        callback,
        amount=99,
        plan_name="Monthly Membership ₹99"
    )

# =========================
# ₹199 PLAN
# =========================
@dp.callback_query(F.data == "plan_199")
async def plan_199_callback(callback: CallbackQuery):
    await create_payment_link_and_send(
        callback,
        amount=199,
        plan_name="Monthly Membership ₹199"
    )

# =========================
# START BOT
# =========================
async def start_bot():
    await dp.start_polling(bot)
