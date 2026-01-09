import time
import razorpay
from backend.app.razorpay_client import client


def create_payment_link(amount_in_rupees: int, user_id: int, plan_id: str):
    """
    Creates a Razorpay payment link with automatic retry if rate limit is hit.
    """

    data = {
        "amount": int(amount_in_rupees) * 100,  # Convert to paise
        "currency": "INR",
        "accept_partial": False,
        "description": f"Subscription payment ({plan_id})",
        "notes": {
            "telegram_id": str(user_id),
            "plan_id": plan_id,
        },
        "notify": {
            "sms": False,
            "email": False
        }
    }

    try:
        return client.payment_link.create(data)

    except razorpay.errors.BadRequestError as e:
        if "Too many requests" in str(e):
            print("⚠️ Razorpay rate-limit hit! Retrying in 1 second...")
            time.sleep(1)
            try:
                return client.payment_link.create(data)
            except Exception as e2:
                print("❌ Second attempt failed:", str(e2))
                return {"error": "rate_limit"}
        else:
            raise e
