from backend.app.razorpay_client import client


def create_payment_link(amount_in_rupees: int, user_id: int, plan_id: str):
    payment_link = client.payment_link.create({
        "amount": amount_in_rupees * 100,  # paise
        "currency": "INR",
        "accept_partial": False,
        "description": f"Subscription payment ({plan_id})",
        "notes": {
            "telegram_user_id": str(user_id),
            "plan_id": plan_id
        },
        "notify": {
            "sms": False,
            "email": False
        }
    })
    return payment_link
