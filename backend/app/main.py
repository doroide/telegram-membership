import os
import asyncio
from fastapi import FastAPI, Request
from aiogram.types import Update

from backend.bot.bot import bot, dp
from backend.app.api.webhook import router as razorpay_router
from backend.app.tasks.expiry_checker import run_expiry_check

app = FastAPI()

# Razorpay Webhook Router
app.include_router(razorpay_router, prefix="/api")


# Telegram Webhook
@app.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    update = Update.model_validate(data)
    await dp.feed_update(bot, update)
    return {"ok": True}


# STARTUP
@app.on_event("startup")
async def on_startup():
    # -------------------------------
    # Set Telegram Webhook
    # -------------------------------
    webhook_url = os.getenv("TELEGRAM_WEBHOOK_URL")

    await bot.delete_webhook(drop_pending_updates=True)
    await bot.set_webhook(webhook_url)

    print("✅ Telegram Webhook Set:", webhook_url)

    # -------------------------------
    # Start expiry background worker
    # -------------------------------
    async def expiry_job():
        while True:
            await run_expiry_check()
            await asyncio.sleep(60 * 60)  # Run every hour

    asyncio.create_task(expiry_job())
    print("⏳ Expiry Checker Started")


# HEALTH CHECK
@app.get("/")
async def root():
    return {"status": "running"}
