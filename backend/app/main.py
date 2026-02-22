import os
from fastapi import FastAPI, Request
from aiogram.types import Update
import asyncio

app = FastAPI()

# ======================================================
# BOT + DISPATCHER
# ======================================================
from backend.bot.bot import bot, dp


# ======================================================
# IMPORT HANDLERS
# ======================================================
from backend.app.tasks.upsell_sender import scheduled_upsell_task
from backend.app.bot.handlers.start import router as start_router
from backend.app.bot.handlers.renew import router as renew_router
from backend.app.bot.handlers.broadcast import router as broadcast_router
from backend.app.bot.handlers.add_channel import router as add_channel_router
from backend.app.bot.handlers.admin_add_user import router as add_user_router
from backend.app.bot.handlers.stats import router as stats_router
from backend.app.bot.handlers.export import router as export_router
from backend.app.bot.handlers.channel_plans import router as channel_plans_router
from backend.app.bot.handlers.myplans import router as myplans_router
from backend.app.bot.handlers.upsell import router as upsell_router
from backend.app.bot.handlers.upsell_stats import router as upsell_stats_router
from backend.app.bot.handlers.admin_panel import router as admin_panel_router
from backend.app.bot.handlers.analytics import router as analytics_router
from backend.app.bot.handlers.autorenew import router as autorenew_router

from backend.app.db.base import Base
from backend.app.db.session import engine

# ======================================================
# REGISTER ROUTERS
# ======================================================
dp.include_router(autorenew_router)
dp.include_router(upsell_router)
dp.include_router(upsell_stats_router)
dp.include_router(start_router)
dp.include_router(add_user_router)
dp.include_router(channel_plans_router)
dp.include_router(myplans_router)
dp.include_router(renew_router)
dp.include_router(broadcast_router)
dp.include_router(add_channel_router)
dp.include_router(stats_router)
dp.include_router(analytics_router)
dp.include_router(export_router)
dp.include_router(admin_panel_router)

print("✅ Aiogram routers registered")

# ======================================================
# RAZORPAY ROUTES
# ======================================================
from backend.app.api.webhook import router as razorpay_router
app.include_router(razorpay_router, prefix="/api")

# ======================================================
# TELEGRAM WEBHOOK
# ======================================================
@app.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    print("🔥 Telegram update received")
    update = Update.model_validate(data)
    await dp.feed_update(bot, update)
    return {"ok": True}

# ======================================================
# STARTUP
# ======================================================
@app.on_event("startup")
async def on_startup():
    print("🚀 App starting...")
    
    # ✅ CREATE TABLES
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Database tables created")
    
    # ✅ SET WEBHOOK
    webhook_url = os.getenv("TELEGRAM_WEBHOOK_URL")
    await bot.delete_webhook(drop_pending_updates=True)
    await bot.set_webhook(webhook_url)
    print("✅ Webhook installed:", webhook_url)
    
    # ✅ START BACKGROUND WORKERS
    from backend.app.tasks.scheduler import start_scheduler
    start_scheduler()
    print("✅ Background workers started")
    
    # ✅ START UPSELL SENDER
    asyncio.create_task(scheduled_upsell_task())
    print("✅ Upsell sender task started")

# ======================================================
# SHUTDOWN
# ======================================================
@app.on_event("shutdown")
async def on_shutdown():
    from backend.app.tasks.scheduler import stop_scheduler
    stop_scheduler()
    print("👋 App shutting down...")

# ======================================================
# HEALTH CHECK
# ======================================================
@app.get("/")
async def root():
    return {"status": "running", "workers": "enabled"}