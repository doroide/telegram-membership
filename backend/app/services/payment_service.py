import os
import razorpay
from sqlalchemy import select
from backend.app.db.models import Channel, Payment

def initialize_razorpay():
    try:
        key_id = os.getenv("RAZORPAY_KEY")
        key_secret = os.getenv("RAZORPAY_SECRET")
        
        print("=" * 50)
        print("🔐 RAZORPAY CREDENTIAL CHECK")
        print("=" * 50)
        if key_id:
            print(f"✅ RAZORPAY_KEY exists: {key_id[:15]}...{key_id[-4:]}")
            print(f"   Length: {len(key_id)} characters")
            print(f"   Starts with 'rzp_': {key_id.startswith('rzp_')}")
            if key_id.startswith("rzp_test_"):
                print("   Mode: TEST")
            elif key_id.startswith("rzp_live_"):
                print("   Mode: LIVE")
            else:
                print("   ⚠️ Mode: UNKNOWN (should be test or live)")
        else:
            print("❌ RAZORPAY_KEY is missing!")
        
        if key_secret:
            print(f"✅ RAZORPAY_SECRET exists: {key_secret[:10]}...{key_secret[-4:]}")
            print(f"   Length: {len(key_secret)} characters")
        else:
            print("❌ RAZORPAY_SECRET is missing!")
        print("=" * 50)
        
        if not key_id or not key_secret:
            print("❌ Cannot initialize - credentials missing!")
            return None
        
        client = razorpay.Client(auth=(key_id, key_secret))
        print("✅ Razorpay Client object created")
        
        try:
            client.payment.all({'count': 1})
            print("✅ Razorpay credentials verified - API test successful!")
        except razorpay.errors.SignatureVerificationError:
            print("❌ Razorpay credentials INVALID - Signature verification failed")
            return None
        except Exception as test_error:
            print(f"⚠️ Razorpay API test: {test_error}")
        
        return client
        
    except Exception as e:
        print(f"⚠️ Razorpay initialization failed: {e}")
        return None

razorpay_client = initialize_razorpay()

async def create_payment_link(user_id: int, channel_id: int, days: int, price: int):
    if not razorpay_client:
        print("❌ Razorpay client not initialized - check environment variables")
        raise Exception("Razorpay not configured. Please contact admin.")
    
    if price <= 0:
        raise Exception("Invalid amount")
    
    if days <= 0:
        raise Exception("Invalid validity period")
    
    validity_display = {
        30: "1 Month",
        90: "3 Months",
        120: "4 Months",
        180: "6 Months",
        365: "1 Year",
        730: "Lifetime"
    }.get(days, f"{days} days")
    
    backend_url = os.getenv('BACKEND_URL', '').rstrip('/')
    callback_url = f"{backend_url}/api/payment/callback" if backend_url else None
    
    print(f"💳 Creating payment link:")
    print(f"   Amount: ₹{price} ({price * 100} paise)")
    print(f"   Days: {days}")
    print(f"   User ID: {user_id}")
    print(f"   Channel ID: {channel_id}")
    print(f"   Callback URL: {callback_url}")
    
    payment_data = {
        "amount": price * 100,
        "currency": "INR",
        "accept_partial": False,
        "description": f"Channel Subscription - {validity_display}",
        "customer": {
            "name": f"User {user_id}",
            "email": f"user{user_id}@telegram.bot"
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
        
        if "amount" in error_msg.lower():
            raise Exception("Invalid amount. Minimum ₹1 required.")
        elif "customer" in error_msg.lower():
            raise Exception("Customer details error. Please try again.")
        elif "authentication" in error_msg.lower() or "auth" in error_msg.lower():
            raise Exception("Invalid Razorpay credentials. Check your API keys in Render settings.")
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