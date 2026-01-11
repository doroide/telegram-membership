import os
import asyncio
from fastapi import FastAPI, Request
from aiogram.types import Update

# Templates for dashboard
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

# Import admin dashboard router
from backend.app.api.routes.admin import router as admin_router

# Import Telegram bot + dispatcher + admin routers
from backend.app.bot.bot import bot, dp, include_admin_routers

# Razorpay webhook router
from backend.app.api.webhook import router as razorpay_router

# Expiry checker (manual worker)
from backend.app.tasks.expiry_checker import run_expiry_check


# ============================
# INIT FASTAPI APP
# ============================

app = FastAPI()

# Dashboard Templates
templates = Jinja2Templates(directory="backend/app/templates")


# ============================
# INCLUDE API ROUTERS
# ============================

# Dashboard /admin/dashboard
app.include_router(admin_router)

# Razorpay webhook
app.include_router(razorpay_router, prefix="/api")


# ============================
# TELEGRAM WEBHOOK ENDPOINT
# ============================

@app.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    update = Update.model_validate(data)

    await dp.feed_update(bot, update)
    return {"ok": True}


# ============================
# STARTUP EVENT
# ============================

@app.on_event("startup")
async def on_startup():

    print("🚀 Startup: Loading admin routers")
    include_admin_routers()   # Load bot admin commands

    # WEBHOOK CONFIGURATION
    webhook_url = os.getenv("TELEGRAM_WEBHOOK_URL")
    current = await bot.get_webhook_info()

    if current.url != webhook_url:
        print("🔗 Installing Telegram webhook...")
        await bot.delete_webhook(drop_pending_updates=True)
        await bot.set_webhook(webhook_url)
        print("✅ Webhook installed:", webhook_url)
    else:
        print("ℹ️ Webhook already installed, skipping")

    # ============================
    # EXPIRY CHECK BACKGROUND TASK
    # ============================

    async def expiry_job():
        while True:
            await run_expiry_check()
            print("⏳ Expiry check completed")
            await asyncio.sleep(3600)   # runs every 1 hour

    asyncio.create_task(expiry_job())
    print("🟢 Expiry Worker Running")


# ============================
# ROOT CHECK ENDPOINT
# ============================

@app.get("/")
async def root():
    return {"status": "running"}
