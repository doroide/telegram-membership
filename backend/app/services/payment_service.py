import razorpay
import os


razorpay_client = razorpay.Client(
    auth=(os.getenv("RAZORPAY_KEY"), os.getenv("RAZORPAY_SECRET"))
)


async def create_payment_link(user_id: int, channel_id: int, days: int, price: int):

    payment = razorpay_client.payment_link.create({
        "amount": price * 100,  # paise
        "currency": "INR",
        "accept_partial": False,
        "description": "Channel Subscription",
        "notes": {
            "telegram_id": user_id,
            "channel_id": channel_id,
            "validity_days": days,
            "amount": price
        }
    })

    return payment["short_url"]
