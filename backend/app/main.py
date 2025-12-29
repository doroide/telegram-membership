from fastapi import FastAPI
import asyncio

from backend.app.api.webhook import router as webhook_router

app.include_router(webhook_router, prefix="/api")

from backend.bot.bot import start_bot

app = FastAPI()

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(start_bot())

@app.get("/")
async def root():
    return {"status": "ok"}
