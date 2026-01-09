import os
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command

# Import PLANS correctly
from backend.app.config.plans import PLANS

# Payment generator
from backend.app.services.payment_service import create_payment_link


# ============================
# BOT INITIALIZATION
# ============================

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not BOT_TOKEN:
    raise RuntimeError("❌ TELEGRAM_BOT_TOKEN missing from environment variables")

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher()


# ============================
# CHANNEL ID
# ============================

CHANNEL_ID = -1002782697491  # Replace with your PRIVATE channel ID


# ============================
# INVITE LINK CREATOR
# ============================

async def get_access_link():
    """Generates a fresh invite link for the user."""
    invite = await bot.create_chat_invite_link(
        CHANNEL_ID,
        creates_join_request=False
    )
    return invite.invite_link


# ============================
# /start — show plans
# ============================

@dp.message(Command("start"))
async def start(message):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=PLANS["plan_199_1m"]["label"], callback_data="plan_199_1m")],
            [InlineKeyboardButton(text=PLANS["plan_399_3m"]["label"], callback_data="plan_399_3m")],
            [InlineKeyboardButton(text=PLANS["plan_599_6m"]["label"], callback_data="plan_599_6m")],
            [InlineKeyboardButton(text=PLANS["plan_799_12m"]["label"], callback_data="plan_799_12m")],
        ]
    )

    await message.answer(
        "🎬 <b>Premium Movies Subscription</b>\n\n"
        "Choose your subscription plan ⬇️",
        reply_markup=keyboard
    )


# ============================
# Callback for plan selection
# ============================

@dp.callback_query(lambda c: c.data in PLANS.keys())
async def handle_plan(callback):
    plan_id = callback.data
    plan = PLANS[plan_id]

    payment = create_payment_link(
        amount_in_rupees=plan["price"],
        user_id=callback.from_user.id,
        plan_id=plan_id
    )

    await callback.message.answer(
        f"📌 <b>Plan Selected</b>\n\n"
        f"📦 {plan['label']}\n"
        f"💰 Price: ₹{plan['price']}\n\n"
        f"🔗 Pay Here:\n{payment['short_url']}\n\n"
        f"After successful payment, you will receive channel access automatically."
    )

    await callback.answer()


# ============================
# ADMIN ROUTERS LOADER
# ============================

def include_admin_routers():
    """Imports admin handlers dynamically to avoid circular imports."""
    from backend.bot.handlers import (
        admin_panel,
        admin_stats,
        admin_extend,
        admin_remove,
        admin_users,
        admin_broadcast,
        admin_expired,
        admin_retry
    )

    dp.include_router(admin_panel.router)
    dp.include_router(admin_stats.router)
    dp.include_router(admin_extend.router)
    dp.include_router(admin_remove.router)
    dp.include_router(admin_users.router)
    dp.include_router(admin_broadcast.router)
    dp.include_router(admin_expired.router)
    dp.include_router(admin_retry.router)
