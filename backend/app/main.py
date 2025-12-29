from fastapi import FastAPI
import asyncio

from backend.bot.bot import start_bot
from backend.app.api.webhook import router as webhook_router

# 1️⃣ Create FastAPI app FIRST
app = FastAPI()

# 2️⃣ Register webhook AFTER app is created
app.include_router(webhook_router, prefix="/api")

# 3️⃣ Start Telegram bot on startup
@app.on_event("startup")
async def startup_event():
    asyncio.create_task(start_bot())

# 4️⃣ Health check
@app.get("/")
async def root():
    return {"status": "ok"}
