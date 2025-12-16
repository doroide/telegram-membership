import os
from dotenv import load_dotenv

# Force load .env from project root
BASE_DIR = os.path.dirname(
    os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )
)

ENV_PATH = os.path.join(BASE_DIR, ".env")
load_dotenv(ENV_PATH)

class Settings:
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
    RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")
    WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")
    DATABASE_URL = os.getenv("DATABASE_URL")
    ADMIN_TELEGRAM_ID = int(os.getenv("ADMIN_TELEGRAM_ID", "0"))
    BASE_URL = os.getenv("BASE_URL")
    CHANNEL_ID = os.getenv("CHANNEL_ID")

settings = Settings()
