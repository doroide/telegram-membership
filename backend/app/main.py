import asyncio
from fastapi import FastAPI

from backend.app.api.webhook import router as webhook_router
from backend.bot.bot import start_bot

app = FastAPI()

# Health check (Railway needs this)
@app.get("/")
async def root():
    return {"status": "ok"}

# Razorpay webhook route
app.include_router(webhook_router, prefix="/webhook")

@app.on_event("startup")
async def startup_event():
    print("FastAPI started successfully")

