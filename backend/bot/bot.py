	import os
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command

# Import PLANS
from backend.app.config.plans import PLANS

# Import Razorpay payment link generator
from backend.app.services.payment_service import create_payment_link


# ======================================================
# BOT INITIALIZATION
# ======================================================

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not BOT_TOKEN:
    raise RuntimeError("❌ TELEGRAM_BOT_TOKEN is missing in ENV")

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher()


# ======================================================
# CHANNEL ID (PRIVATE CHANNEL)
# ======================================================

CHANNEL_ID = -1002782697491   # UPDATE with your channel ID


# ======================================================
# GENERATE CHANNEL INVITE LINK
# ======================================================

async def get_access_link():
    """Generate fresh invite link every time."""
    invite = await bot.create_chat_invite_link(
        CHANNEL_ID,
        creates_join_request=False
    )
    return invite.invite_link


# ======================================================
# COMMAND: /start
# ======================================================

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


# ======================================================
# PLAN SELECTION HANDLER
# ======================================================

@dp.callback_query(lambda c: c.data in PLANS.keys())
async def handle_plan(callback):
    plan_id = callback.data
    plan = PLANS[plan_id]

    # Prevent double clicks
    await callback.answer("Generating payment link…", show_alert=False)

    # Let user know bot is working
    await callback.message.answer("⏳ Creating secure payment link...")

    # Generate Razorpay payment link with error protection
    try:
        payment = create_payment_link(
            amount_in_rupees=plan["price"],
            user_id=callback.from_user.id,
            plan_id=plan_id
        )
    except Exception as e:
        await callback.message.answer(
            "⚠️ Unable to generate payment link.\n"
            "Please wait and try again."
        )
        return

    # Razorpay rate limit handling
    if isinstance(payment, dict) and payment.get("error") == "rate_limit":
        await callback.message.answer(
            "⚠️ Too many requests.\n"
            "Please wait 10 seconds and try again."
        )
        return

    # Validate response
    if "short_url" not in payment:
        await callback.message.answer(
            "❌ Payment link could not be generated.\n"
            "Try again later."
        )
        return

    # Success → Send payment link
    await callback.message.answer(
        f"🧾 <b>Plan Selected</b>\n\n"
        f"📦 {plan['label']}\n"
        f"💰 Price: ₹{plan['price']}\n\n"
        f"🔗 <b>Pay Here:</b>\n{payment['short_url']}\n\n"
        f"Once payment is completed, you will receive channel access automatically."
    )


# ======================================================
# INCLUDE ADMIN ROUTERS (dynamic import)
# ======================================================

def include_admin_routers():
    """Load admin routers safely (prevents circular imports)."""

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

