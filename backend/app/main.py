import os
import asyncio
from fastapi import FastAPI, Request
from aiogram.types import Update

from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles


# ======================================================
# CREATE APP FIRST
# ======================================================

app = FastAPI()

templates = Jinja2Templates(directory="backend/app/templates")


# ======================================================
# IMPORT BOT + DP FIRST  ⭐ IMPORTANT
# ======================================================

from backend.bot.bot import bot, dp, include_admin_routers


# ======================================================
# NOW IMPORT HANDLERS (after dp exists)
# ======================================================

from backend.app.bot.handlers.stats import router as stats_router
from backend.app.bot.handlers.admin_add_user import router as add_user_router
from backend.app.bot.handlers.start import router as start_router
from backend.app.bot.handlers.add_channel import router as add_channel_router
from backend.app.bot.handlers.broadcast import router as broadcast_router
from backend.app.bot.handlers.renew import router as renew_router
from backend.app.bot.handlers.user_plans import router as plans_router
from backend.app.bot.handlers.myplans import router as myplans_router


# ======================================================
# REGISTER AIROGRAM ROUTERS  ⭐ ONLY HERE
# ======================================================

dp.include_router(start_router)
dp.include_router(plans_router)
dp.include_router(renew_router)
dp.include_router(myplans_router)
dp.include_router(broadcast_router)
dp.include_router(add_channel_router)
dp.include_router(add_user_router)
dp.include_router(stats_router)


# ======================================================
# FASTAPI ROUTES
# ======================================================

from backend.app.api.routes.admin import router as admin_router
from backend.app.api.webhook import router as razorpay_router
from backend.app.tasks.expiry_checker import run_expiry_check


app.include_router(razorpay_router, prefix="/api")


# ======================================================
# TELEGRAM WEBHOOK
# ======================================================

@app.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    update = Update.model_validate(data)

    await dp.feed_update(bot, update)
    return {"ok": True}


# ======================================================
# STARTUP
# ======================================================

@app.on_event("startup")
async def on_startup():

    print("🚀 Startup: Loading admin routers")
  

    webhook_url = os.getenv("TELEGRAM_WEBHOOK_URL")
    current = await bot.get_webhook_info()

    if current.url != webhook_url:
        print("🔗 Installing Telegram webhook...")
        await bot.delete_webhook(drop_pending_updates=True)
        await bot.set_webhook(webhook_url)
        print("✅ Webhook installed:", webhook_url)
    else:
        print("ℹ️ Webhook already installed")

    async def expiry_job():
        while True:
            await run_expiry_check()
            print("⏳ Expiry check completed")
            await asyncio.sleep(3600)

    asyncio.create_task(expiry_job())
    print("🟢 Expiry Worker Running")


# ======================================================
# HEALTH CHECK
# ======================================================

@app.get("/")
async def root():
    return {"status": "running"}
