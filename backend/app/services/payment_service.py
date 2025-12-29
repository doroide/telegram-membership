from backend.app.razorpay_client import client


def create_order(amount_in_rupees: int, user_id: int, plan_id: str):
    order = client.order.create({
        "amount": amount_in_rupees * 100,  # paise
        "currency": "INR",
        "payment_capture": 1,
        "notes": {
            "telegram_user_id": user_id,
            "plan_id": plan_id
        }
    })
    return order
