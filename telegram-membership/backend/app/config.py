import os
from pydantic import BaseSettings
from dotenv import load_dotenv

# Calculate project root (telegram-membership)
BASE_DIR = os.path.dirname(
    os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )
)

ENV_PATH = os.path.join(BASE_DIR, ".env")

# Force load .env
load_dotenv(ENV_PATH)

class Settings(BaseSettings):
    TELEGRAM_BOT_TOKEN: str
    RAZORPAY_KEY_ID: str
    RAZORPAY_KEY_SECRET: str
    WEBHOOK_SECRET: str
    DATABASE_URL: str
    ADMIN_TELEGRAM_ID: int
    BASE_URL: str
    CHANNEL_ID: str

settings = Settings()
