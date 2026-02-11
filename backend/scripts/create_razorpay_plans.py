import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import razorpay

# Initialize Razorpay client - use environment variables directly
RAZORPAY_KEY = os.getenv("RAZORPAY_KEY")
RAZORPAY_SECRET = os.getenv("RAZORPAY_SECRET")

# If not in environment, try to get from user input
if not RAZORPAY_KEY or not RAZORPAY_SECRET:
    print("=" * 60)
    print("⚠️ Razorpay credentials not found in environment variables")
    print("=" * 60)
    print()
    
    print("Please enter your Razorpay credentials:")
    RAZORPAY_KEY = input("RAZORPAY_KEY: ").strip()
    RAZORPAY_SECRET = input("RAZORPAY_SECRET: ").strip()
    
    if not RAZORPAY_KEY or not RAZORPAY_SECRET:
        print("\n❌ Error: Both RAZORPAY_KEY and RAZORPAY_SECRET are required")
        sys.exit(1)
    
    print()

razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY, RAZORPAY_SECRET))

# =====================================================
# PLAN DEFINITIONS
# =====================================================

PLAN_CONFIGS = {
    # 1 MONTH PLANS
    "1M_T1": {
        "period": "monthly",
        "interval": 1,
        "amount": 4900,  # ₹49
        "name": "1 Month - Tier 1 (Auto-Renewal)",
        "description": "1 Month subscription - Tier 1 pricing"
    },
    "1M_T2": {
        "period": "monthly",
        "interval": 1,
        "amount": 9900,  # ₹99
        "name": "1 Month - Tier 2 (Auto-Renewal)",
        "description": "1 Month subscription - Tier 2 pricing"
    },
    "1M_T3": {
        "period": "monthly",
        "interval": 1,
        "amount": 19900,  # ₹199
        "name": "1 Month - Tier 3 (Auto-Renewal)",
        "description": "1 Month subscription - Tier 3 pricing"
    },
    "1M_T4": {
        "period": "monthly",
        "interval": 1,
        "amount": 29900,  # ₹299
        "name": "1 Month - Tier 4 (Auto-Renewal)",
        "description": "1 Month subscription - Tier 4 pricing"
    },
    
    # 3 MONTHS PLANS
    "3M_T1": {
        "period": "monthly",
        "interval": 3,
        "amount": 14900,  # ₹149
        "name": "3 Months - Tier 1 (Auto-Renewal)",
        "description": "3 Months subscription - Tier 1 pricing"
    },
    "3M_T2": {
        "period": "monthly",
        "interval": 3,
        "amount": 29900,  # ₹299
        "name": "3 Months - Tier 2 (Auto-Renewal)",
        "description": "3 Months subscription - Tier 2 pricing"
    },
    "3M_T3": {
        "period": "monthly",
        "interval": 3,
        "amount": 59900,  # ₹599
        "name": "3 Months - Tier 3 (Auto-Renewal)",
        "description": "3 Months subscription - Tier 3 pricing"
    },
    "3M_T4": {
        "period": "monthly",
        "interval": 3,
        "amount": 89900,  # ₹899
        "name": "3 Months - Tier 4 (Auto-Renewal)",
        "description": "3 Months subscription - Tier 4 pricing"
    },
    
    # 4 MONTHS PLANS
    "4M_T1": {
        "period": "monthly",
        "interval": 4,
        "amount": 19900,  # ₹199
        "name": "4 Months - Tier 1 (Auto-Renewal)",
        "description": "4 Months subscription - Tier 1 pricing"
    },
    "4M_T2": {
        "period": "monthly",
        "interval": 4,
        "amount": 39900,  # ₹399
        "name": "4 Months - Tier 2 (Auto-Renewal)",
        "description": "4 Months subscription - Tier 2 pricing"
    },
    "4M_T3": {
        "period": "monthly",
        "interval": 4,
        "amount": 79900,  # ₹799
        "name": "4 Months - Tier 3 (Auto-Renewal)",
        "description": "4 Months subscription - Tier 3 pricing"
    },
    "4M_T4": {
        "period": "monthly",
        "interval": 4,
        "amount": 119900,  # ₹1199
        "name": "4 Months - Tier 4 (Auto-Renewal)",
        "description": "4 Months subscription - Tier 4 pricing"
    },
    
    # 6 MONTHS PLANS
    "6M_T1": {
        "period": "monthly",
        "interval": 6,
        "amount": 29900,  # ₹299
        "name": "6 Months - Tier 1 (Auto-Renewal)",
        "description": "6 Months subscription - Tier 1 pricing"
    },
    "6M_T2": {
        "period": "monthly",
        "interval": 6,
        "amount": 59900,  # ₹599
        "name": "6 Months - Tier 2 (Auto-Renewal)",
        "description": "6 Months subscription - Tier 2 pricing"
    },
    "6M_T3": {
        "period": "monthly",
        "interval": 6,
        "amount": 119900,  # ₹1199
        "name": "6 Months - Tier 3 (Auto-Renewal)",
        "description": "6 Months subscription - Tier 3 pricing"
    },
    "6M_T4": {
        "period": "monthly",
        "interval": 6,
        "amount": 179900,  # ₹1799
        "name": "6 Months - Tier 4 (Auto-Renewal)",
        "description": "6 Months subscription - Tier 4 pricing"
    },
    
    # 1 YEAR PLANS
    "1Y_T1": {
        "period": "yearly",
        "interval": 1,
        "amount": 59900,  # ₹599
        "name": "1 Year - Tier 1 (Auto-Renewal)",
        "description": "1 Year subscription - Tier 1 pricing"
    },
    "1Y_T2": {
        "period": "yearly",
        "interval": 1,
        "amount": 119900,  # ₹1199
        "name": "1 Year - Tier 2 (Auto-Renewal)",
        "description": "1 Year subscription - Tier 2 pricing"
    },
    "1Y_T3": {
        "period": "yearly",
        "interval": 1,
        "amount": 239900,  # ₹2399
        "name": "1 Year - Tier 3 (Auto-Renewal)",
        "description": "1 Year subscription - Tier 3 pricing"
    },
    "1Y_T4": {
        "period": "yearly",
        "interval": 1,
        "amount": 359900,  # ₹3599
        "name": "1 Year - Tier 4 (Auto-Renewal)",
        "description": "1 Year subscription - Tier 4 pricing"
    }
}


def create_plans():
    """Create all Razorpay subscription plans"""
    
    print("=" * 60)
    print("🔄 CREATING RAZORPAY SUBSCRIPTION PLANS")
    print("=" * 60)
    print()
    
    created_plans = {}
    failed_plans = []
    
    for plan_key, config in PLAN_CONFIGS.items():
        try:
            print(f"Creating: {config['name']}...")
            
            plan = razorpay_client.plan.create({
                "period": config["period"],
                "interval": config["interval"],
                "item": {
                    "name": config["name"],
                    "description": config["description"],
                    "amount": config["amount"],
                    "currency": "INR"
                },
                "notes": {
                    "plan_key": plan_key,
                    "tier": plan_key.split("_")[1],
                    "duration": plan_key.split("_")[0]
                }
            })
            
            created_plans[plan_key] = plan["id"]
            print(f"✅ Created: {plan['id']}")
            print()
            
        except razorpay.errors.BadRequestError as e:
            error_msg = str(e)
            if "already exists" in error_msg.lower():
                print(f"⚠️ Plan already exists, skipping...")
            else:
                print(f"❌ Error: {error_msg}")
                failed_plans.append(plan_key)
            print()
            
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            failed_plans.append(plan_key)
            print()
    
    # =====================================================
    # DISPLAY RESULTS
    # =====================================================
    
    print("=" * 60)
    print("📋 RESULTS")
    print("=" * 60)
    print()
    
    if created_plans:
        print(f"✅ Successfully created {len(created_plans)} plans")
        print()
        
        # Generate .env format
        print("=" * 60)
        print("📝 ADD THESE TO RENDER ENVIRONMENT VARIABLES:")
        print("=" * 60)
        print()
        
        for plan_key, plan_id in created_plans.items():
            env_var = f"RAZORPAY_PLAN_{plan_key}"
            print(f'{env_var}={plan_id}')
        
        print()
        print("=" * 60)
        print()
        
        # Generate Python dict format
        print("=" * 60)
        print("📝 OR SAVE THIS TO A FILE:")
        print("=" * 60)
        print()
        print("# Save this to: backend/config/razorpay_plans.py")
        print()
        print("RAZORPAY_PLANS = {")
        for plan_key, plan_id in created_plans.items():
            print(f'    "{plan_key}": "{plan_id}",')
        print("}")
        print()
        
    if failed_plans:
        print(f"❌ Failed to create {len(failed_plans)} plans:")
        for plan_key in failed_plans:
            print(f"   - {plan_key}")
        print()
    
    print("=" * 60)
    print("✅ DONE!")
    print("=" * 60)


if __name__ == "__main__":
    try:
        create_plans()
    except KeyboardInterrupt:
        print("\n\n⚠️ Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)