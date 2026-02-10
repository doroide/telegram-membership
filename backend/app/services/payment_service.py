import os
import razorpay
from sqlalchemy import select
from backend.app.db.models import Channel, Payment

# =====================================================
# RAZORPAY CLIENT INITIALIZATION
# =====================================================

def initialize_razorpay():
    """Initialize Razorpay client with proper error handling"""
    try:
        # ✅ FIXED: Use correct environment variable names
        key_id = os.getenv("RAZORPAY_KEY")  # Changed from RAZORPAY_KEY_ID
        key_secret = os.getenv("RAZORPAY_SECRET")  # Changed from RAZORPAY_KEY_SECRET
        
        # Debug logging
        print(f"🔑 RAZORPAY_KEY: {key_id[:10]}..." if key_id else "❌ RAZORPAY_KEY is None")
        print(f"🔑 RAZORPAY_SECRET: {'***' if key_secret else '❌ None'}")
        
        if not key_id or not key_secret:
            print("❌ Razorpay credentials missing in environment variables!")
            return None
        
        if not key_id.startswith("rzp_"):
            print(f"⚠️ Invalid RAZORPAY_KEY format: {key_id[:10]}... (should start with 'rzp_')")
            return None
        
        client = razorpay.Client(auth=(key_id, key_secret))
        print("✅ Razorpay client initialized successfully")
        return client
        
    except Exception as e:
        print(f"⚠️ Razorpay initialization failed: {e}")
        return None


# Initialize client
razorpay_client = initialize_razorpay()


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
        print("❌ Razorpay client not initialized - check environment variables")
        raise Exception("Razorpay not configured. Please contact admin.")
    
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
        print(f"💳 Creating payment link: ₹{price} for {days} days")
        payment_link = razorpay_client.payment_link.create(payment_data)
        print(f"✅ Payment link created: {payment_link['short_url']}")
        return payment_link["short_url"]
        
    except razorpay.errors.BadRequestError as e:
        print(f"❌ Razorpay BadRequest: {e}")
        raise Exception("Invalid payment request. Please try again.")
        
    except razorpay.errors.SignatureVerificationError as e:
        print(f"❌ Razorpay Signature Error: {e}")
        raise Exception("Authentication failed. Please contact admin.")
        
    except Exception as e:
        print(f"❌ Razorpay payment link creation failed: {e}")
        print(f"Error type: {type(e).__name__}")
        raise Exception(f"Failed to create payment link: {str(e)}")


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