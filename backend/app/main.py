import os
from fastapi import FastAPI, Request
from aiogram.types import Update

from backend.bot.bot import bot, dp
from backend.app.api.webhook import router as razorpay_router

# ===============================
# Create FastAPI app
# ===============================
app = FastAPI()

# ===============================
# Razorpay Webhook Route
# ===============================
app.include_router(razorpay_router, prefix="/api")

# ===============================
# Telegram Webhook Route
# ===============================
@app.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    update = Update.model_validate(await request.json())
    await dp.feed_update(bot, update)
    return {"ok": True}

# ===============================
# Startup: Set Telegram Webhook
# ===============================
@app.on_event("startup")
async def on_startup():
    webhook_url = os.getenv("TELEGRAM_WEBHOOK_URL")
    if not webhook_url:
        raise RuntimeError("TELEGRAM_WEBHOOK_URL is missing")

    # Remove any existing webhook/polling
    await bot.delete_webhook(drop_pending_updates=True)

    # Set Telegram webhook
    await bot.set_webhook(webhook_url)

    print("✅ Telegram webhook set to:", webhook_url)

# ===============================
# Health Check
# ===============================
@app.get("/")
async def root():
    return {"status": "ok"}
