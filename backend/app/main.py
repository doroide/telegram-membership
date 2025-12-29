from fastapi import FastAPI
import os
from backend.bot.bot import bot, dp

app = FastAPI()

@app.on_event("startup")
async def startup():
    webhook_url = os.getenv("TELEGRAM_WEBHOOK_URL")
    await bot.set_webhook(webhook_url)
