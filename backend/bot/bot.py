import os
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command

# PLANS
from backend.app.config.plans import PLANS

# PAYMENT LINK GENERATOR
from backend.app.services.payment_service import create_payment_link


# ============================
# BOT INITIALIZATION
# ============================

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not BOT_TOKEN:
    raise RuntimeError("❌ TELEGRAM_BOT_TOKEN not found in environment variables")

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher()


# ============================
# CHANNEL ID
# ============================

CHANNEL_ID = -1002782697491  # <-- update to your private channel ID


# ============================
# INVITE LINK GENERATOR
# ============================

async def get_access_link():
    """Create a fresh invite link for the channel."""
    invite = await bot.create_chat_invite_link(
        CHANNEL_ID,
        creates_join_request=False
    )
    return invite.invite_link


# ============================
# /start COMMAND
# ============================

@dp.message(Command("start"))
async def start(message):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=PLANS["plan_199_30d"]["label"], callback_data="plan_199_30d")],
            [InlineKeyboardButton(text=PLANS["plan_499_90d"]["label"], callback_data="plan_499_90d")],
            [InlineKeyboardButton(text=PLANS["plan_799_180d"]["label"], callback_data="plan_799_180d")],
        ]
    )

    await message.answer(
        "🎬 <b>Premium Movies Subscription</b>\n\n"
        "Choose your subscription plan ⬇️",
        reply_markup=keyboard
    )


# ============================
# PLAN SELECTION HANDLER
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
# ADMIN ROUTER LOADER
# ============================

def include_admin_routers():
    """Import admin routers dynamically to avoid circular imports."""

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
