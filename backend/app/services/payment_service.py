import os
import razorpay
from sqlalchemy import select
from backend.app.db.models import Channel, Payment

# Initialize Razorpay client
try:
    RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
    RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")
    razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
except Exception as e:
    print(f"⚠️ Razorpay initialization failed: {e}")
    razorpay_client = None  # ✅ Added this line

# =====================================================
# PAYMENT LINK CREATION
# =====================================================

async def create_payment_link(user_id: int, channel_id: int, days: int, price: int):
    """
    Create a Razorpay payment link for user subscription
    
    Args:
        user_id: Internal user ID
        channel_id: Channel ID
        days: Validity days
        price: Amount in rupees
    
    Returns:
        Payment link URL
    """
    if not razorpay_client:
        raise Exception("Razorpay not configured")
    
    # Format description
    validity_display = {
        30: "1 Month",
        90: "3 Months",
        120: "4 Months",
        180: "6 Months",
        365: "1 Year",
        730: "Lifetime"
    }.get(days, f"{days} days")
    
    # Create payment link
    payment_data = {
        "amount": price * 100,  # Convert to paise
        "currency": "INR",
        "description": f"Channel Subscription - {validity_display}",
        "customer": {
            "notify": 1
        },
        "notes": {
            "user_id": str(user_id),
            "channel_id": str(channel_id),
            "validity_days": str(days)
        },
        "callback_url": f"{os.getenv('BACKEND_URL', '')}/api/payment/callback",
        "callback_method": "get"
    }
    
    try:
        payment_link = razorpay_client.payment_link.create(payment_data)
        return payment_link["short_url"]
    except Exception as e:
        print(f"❌ Razorpay payment link creation failed: {e}")
        raise Exception("Failed to create payment link")


# =====================================================
# CHANNEL SERVICE
# =====================================================

class ChannelService:
    @staticmethod
    async def get_active_channels(session):
        result = await session.execute(
            select(Channel).where(Channel.is_active == True)
        )
        return result.scalars().all()
    
    @staticmethod
    async def get_channel(session, channel_id: int):
        return await session.get(Channel, channel_id)
    
    @staticmethod
    async def disable_channel(session, channel_id: int):
        channel = await session.get(Channel, channel_id)
        if channel:
            channel.is_active = False
            await session.commit()