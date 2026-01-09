import time
import razorpay
from backend.app.razorpay_client import client


def create_payment_link(amount_in_rupees: int, user_id: int, plan_id: str):
    """
    Creates Razorpay payment link with retry handling for rate limits.
    """

    data = {
        "amount": int(amount_in_rupees) * 100,       # convert rupees → paise
        "currency": "INR",
        "accept_partial": False,
        "description": f"Subscription payment ({plan_id})",

        # IMPORTANT: telegram_id should be INTEGER, not string
        "notes": {
            "telegram_id": int(user_id),
            "plan_id": plan_id,
        },

        "notify": {
            "sms": False,
            "email": False
        }
    }

    try:
        # Attempt 1
        return client.payment_link.create(data)

    except razorpay.errors.BadRequestError as e:
        if "Too many requests" in str(e):
            print("⚠️ Razorpay rate-limit hit! Retrying in 1 second...")
            time.sleep(1)
            try:
                # Attempt 2 after 1-second pause
                return client.payment_link.create(data)

            except Exception as e2:
                print("❌ Second attempt failed:", str(e2))
                return {"error": "rate_limit"}

        # If it's not rate limit, raise error normally
        raise e
