import os
import asyncio
from datetime import datetime
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from sqlalchemy import select

# Import PLANS
from backend.app.config.plans import PLANS

# Import payment generator
from backend.app.services.payment_service import create_payment_link

# DB session + model
from backend.app.db.session import async_session
from backend.app.db.models import User


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

CHANNEL_ID = -1002782697491       # Your PRIVATE channel ID


# ============================
# INVITE LINK CREATOR
# ============================

async def get_access_link():
    """Generate a fresh invite link."""
    invite = await bot.create_chat_invite_link(
        CHANNEL_ID,
        creates_join_request=False
    )
    return invite.invite_link


# ============================
# /start — Subscription Plans
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
        "Choose your plan below 👇",
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
        f"🔗 Pay here:\n{payment['short_url']}\n\n"
        f"After payment, channel access will be sent automatically."
    )

    await callback.answer()


# ============================
# AUTO-REMOVE EXPIRED USERS
# ============================

async def remove_expired_users():
    """Check DB & remove expired users from channel automatically."""
    async with async_session() as session:
        result = await session.execute(select(User))
        users = result.scalars().all()

    for u in users:
        if u.expiry_date and u.expiry_date < datetime.now() and u.is_active:
            u.is_active = False

            # Remove from channel
            try:
                await bot.ban_chat_member(CHANNEL_ID, int(u.telegram_id))
            except:
                pass

            # Unban to allow future rejoin
            try:
                await bot.unban_chat_member(CHANNEL_ID, int(u.telegram_id))
            except:
                pass

            # Update database
            async with async_session() as session:
                session.add(u)
                await session.commit()

    print("⏳ Auto-check complete: expired users removed.")


async def scheduler():
    """Runs auto-removal every hour."""
    while True:
        await remove_expired_users()
        await asyncio.sleep(3600)   # every 1 hour


# ============================
# LOAD ALL ADMIN ROUTERS
# ============================

def include_admin_routers():
    from backend.bot.handlers import (
        admin_broadcast,
        admin_expired,
        admin_extend,
        admin_notify,
        admin_panel,
        admin_remove,
        admin_retry,
        admin_stats,
        admin_users,
        start
    )

    dp.include_router(admin_broadcast.router)
    dp.include_router(admin_expired.router)
    dp.include_router(admin_extend.router)
    dp.include_router(admin_notify.router)
    dp.include_router(admin_panel.router)
    dp.include_router(admin_remove.router)
    dp.include_router(admin_retry.router)
    dp.include_router(admin_stats.router)
    dp.include_router(admin_users.router)
    dp.include_router(start.router)


# ============================
# ON STARTUP
# ============================

async def on_startup():
    include_admin_routers()
    asyncio.create_task(scheduler())
    print("🚀 Bot started successfully with auto-expiry scheduler!")


