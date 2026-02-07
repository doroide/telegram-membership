import razorpay
import os
from asyncio import to_thread

razorpay_client = razorpay.Client(
    auth=(os.getenv("RAZORPAY_KEY"), os.getenv("RAZORPAY_SECRET"))
)

async def create_payment_link(user_id: int, channel_id: int, days: int, price: int):
    """
    Create Razorpay payment link for channel subscription
    """
    try:
        # Run sync Razorpay call in thread pool
        payment = await to_thread(
            razorpay_client.payment_link.create,
            {
                "amount": price * 100,  # convert to paise
                "currency": "INR",
                "accept_partial": False,
                "description": f"Channel Subscription - {days} days",
                "notes": {
                    "telegram_id": str(user_id),
                    "channel_id": str(channel_id),
                    "validity_days": str(days),
                    "amount": str(price)
                }
            }
        )
        
        print(f"✅ Payment link created: {payment.get('short_url')}")
        return payment["short_url"]
    
    except Exception as e:
        print(f"❌ Razorpay error: {e}")
        raise