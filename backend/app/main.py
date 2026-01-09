import os
import asyncio
from fastapi import FastAPI, Request
from aiogram.types import Update

from backend.bot.bot import bot, dp, include_admin_routers
from backend.app.api.webhook import router as razorpay_router
from backend.app.tasks.expiry_checker import run_expiry_check

app = FastAPI()

# Razorpay webhook
app.include_router(razorpay_router, prefix="/api")


@app.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    update = Update.model_validate(data)
    await dp.feed_update(bot, update)
    return {"ok": True}


@app.on_event("startup")
async def on_startup():

    print("🚀 Startup: Loading admin routers")
    include_admin_routers()

    webhook_url = os.getenv("TELEGRAM_WEBHOOK_URL")

    # Check webhook only ONCE
    current = await bot.get_webhook_info()

    if current.url != webhook_url:
        print("🔗 Installing webhook...")
        await bot.delete_webhook(drop_pending_updates=True)
        await bot.set_webhook(webhook_url)
        print("✅ Webhook installed:", webhook_url)
    else:
        print("ℹ️ Webhook already installed, skipping")

    # Background expiry worker
    async def expiry_job():
        while True:
            await run_expiry_check()
            print("⏳ Expiry check completed")
            await asyncio.sleep(3600)

    asyncio.create_task(expiry_job())
    print("🟢 Expiry Worker Running")


@app.get("/")
async def root():
    return {"status": "running"}
