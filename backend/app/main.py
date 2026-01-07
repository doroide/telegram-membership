import os
import asyncio
from fastapi import FastAPI, Request
from aiogram.types import Update

from backend.app.services.reminder_service import reminder_loop
from backend.bot.bot import bot, dp
from backend.app.api.webhook import router as razorpay_router
from backend.app.tasks.expiry_checker import run_expiry_check
from backend.bot.handlers.admin_broadcast import daily_broadcast_scheduler

app = FastAPI()

# Razorpay webhook
app.include_router(razorpay_router, prefix="/api")

# Telegram webhook
@app.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    update = Update.model_validate(await request.json())
    await dp.feed_update(bot, update)
    return {"ok": True}

# ✅ SINGLE, CORRECT STARTUP EVENT
@app.on_event("startup")
async def on_startup():
    # 1️⃣ Set Telegram webhook
    webhook_url = os.getenv("TELEGRAM_WEBHOOK_URL")
    await bot.delete_webhook(drop_pending_updates=True)
    await bot.set_webhook(webhook_url)

    print("✅ Telegram webhook set")

 # 2️⃣ Start expiry checker
   async def expiry_job():
      while True:
          await run_expiry_check()       # run the checker
          await asyncio.sleep(24 * 60 * 60)  # wait 24 hours

   asyncio.create_task(expiry_job())
    
   async def on_startup():
   

   asyncio.create_task(daily_broadcast_scheduler())

    # 2️⃣ Start expiry checker (daily)
    async def daily_expiry_job():
        while True:
            await run_expiry_check()
            await asyncio.sleep(24 * 60 * 60)  # 24h

    asyncio.create_task(daily_expiry_job())

    # 3️⃣ Start reminder loop (hourly)
    asyncio.create_task(reminder_loop())

# Health check
@app.get("/")
async def root():
    return {"status": "ok"}
