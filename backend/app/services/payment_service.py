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
        key_id = os.getenv("RAZORPAY_KEY")
        key_secret = os.getenv("RAZORPAY_SECRET")
        
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
    
    # Validate inputs
    if price <= 0:
        raise Exception("Invalid amount")
    
    if days <= 0:
        raise Exception("Invalid validity period")
    
    # Format description
    validity_display = {
        30: "1 Month",
        90: "3 Months",
        120: "4 Months",
        180: "6 Months",
        365: "1 Year",
        730: "Lifetime"
    }.get(days, f"{days} days")
    
    # Get callback URL
    backend_url = os.getenv('BACKEND_URL', '').rstrip('/')
    callback_url = f"{backend_url}/api/payment/callback" if backend_url else None
    
    print(f"💳 Creating payment link:")
    print(f"   Amount: ₹{price} ({price * 100} paise)")
    print(f"   Days: {days}")
    print(f"   User ID: {user_id}")
    print(f"   Channel ID: {channel_id}")
    print(f"   Callback URL: {callback_url}")
    
    # ✅ FIXED: Proper Razorpay payment link format
    payment_data = {
        "amount": price * 100,  # Amount in paise
        "currency": "INR",
        "accept_partial": False,
        "description": f"Channel Subscription - {validity_display}",
        "customer": {
            "name": f"User {user_id}",
            "email": f"user{user_id}@telegram.bot",
            "contact": "+919999999999"  # Dummy number
        },
        "notify": {
            "sms": False,
            "email": False
        },
        "reminder_enable": False,
        "notes": {
            "user_id": str(user_id),
            "channel_id": str(channel_id),
            "validity_days": str(days),
            "platform": "telegram_bot"
        }
    }
    
    # Only add callback if URL exists
    if callback_url:
        payment_data["callback_url"] = callback_url
        payment_data["callback_method"] = "get"
    
    try:
        print(f"📤 Sending request to Razorpay...")
        payment_link = razorpay_client.payment_link.create(payment_data)
        print(f"✅ Payment link created successfully!")
        print(f"   Link ID: {payment_link.get('id', 'N/A')}")
        print(f"   Short URL: {payment_link.get('short_url', 'N/A')}")
        return payment_link["short_url"]
        
    except razorpay.errors.BadRequestError as e:
        error_msg = str(e)
        print(f"❌ Razorpay BadRequest Error:")
        print(f"   {error_msg}")
        
        # Parse error for better user message
        if "amount" in error_msg.lower():
            raise Exception("Invalid amount. Minimum ₹1 required.")
        elif "customer" in error_msg.lower():
            raise Exception("Customer details error. Please try again.")
        else:
            raise Exception(f"Payment error: {error_msg}")
        
    except razorpay.errors.SignatureVerificationError as e:
        print(f"❌ Razorpay Signature Error: {e}")
        raise Exception("Authentication failed. Please contact admin.")
        
    except Exception as e:
        print(f"❌ Razorpay payment link creation failed:")
        print(f"   Error: {e}")
        print(f"   Type: {type(e).__name__}")
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
```

---

## 🎯 **Key Changes:**

1. ✅ Added `accept_partial: False`
2. ✅ Added proper `customer` object with name/email/contact
3. ✅ Added `notify` and `reminder_enable` fields
4. ✅ Better error logging to see exact Razorpay error
5. ✅ Validates amount and days before sending to Razorpay

---

## 📋 **After Deploy, Check Logs For:**

You should see detailed logs like:
```
💳 Creating payment link:
   Amount: ₹199 (19900 paise)
   Days: 30
   User ID: 1
   Channel ID: 1
   Callback URL: https://your-app.onrender.com/api/payment/callback
📤 Sending request to Razorpay...
✅ Payment link created successfully!
```

---

## 🚨 **If Still Fails:**

**Send me the EXACT error from Render logs** that appears after this line:
```
❌ Razorpay BadRequest Error: