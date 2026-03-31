# =========================================================
# SYSTEM 1 - TIER ENGINE
# =========================================================

from sqlalchemy import select, func
from backend.app.db.models import Membership

# =========================================================
# TIER PRICING CONFIGURATION
# =========================================================

TIER_PLANS = {
    1: {
        "name": "Tier 1 (Budget)",
        "plans": [
            {"validity": "1M", "days": 30, "price": 49},
            {"validity": "4M", "days": 120, "price": 199},
            {"validity": "6M", "days": 180, "price": 299},
            {"validity": "1Y", "days": 365, "price": 599},
            {"validity": "Lifetime", "days": 9999, "price": 999},
        ],
    },
    2: {
        "name": "Tier 2 (Standard)",
        "plans": [
            {"validity": "1M", "days": 30, "price": 99},
            {"validity": "4M", "days": 120, "price": 299},
            {"validity": "6M", "days": 180, "price": 499},
            {"validity": "1Y", "days": 365, "price": 799},
            {"validity": "Lifetime", "days": 9999, "price": 999},
        ],
    },
    3: {
        "name": "Tier 3 (Premium)",
        "plans": [
            {"validity": "1M", "days": 30, "price": 199},
            {"validity": "3M", "days": 90, "price": 399},
            {"validity": "6M", "days": 180, "price": 599},
            {"validity": "1Y", "days": 365, "price": 799},
            {"validity": "Lifetime", "days": 9999, "price": 999},
        ],
    },
    4: {
        "name": "Tier 4 (Elite)",
        "plans": [
            {"validity": "1M", "days": 30, "price": 299},
            {"validity": "3M", "days": 90, "price": 599},
            {"validity": "6M", "days": 180, "price": 899},
            {"validity": "1Y", "days": 365, "price": 1199},
            {"validity": "Lifetime", "days": 9999, "price": 1499},
        ],
    },
}


# =========================================================
# TIER CALCULATION
# =========================================================
def get_price_for_validity(tier: int, validity_days: int):
    """Get price for a specific tier and validity days"""
    plans = TIER_PLANS.get(tier, {}).get("plans", [])
    for plan in plans:
        if plan["days"] == validity_days:
            return plan["price"]
    return None

def calculate_tier_from_amount(amount: int) -> int:
    if amount >= 299:
        return 4
    elif amount >= 199:
        return 3
    elif amount >= 99:
        return 2
    else:
        return 1


# =========================================================
# LIFETIME ESCALATION
# =========================================================

async def get_lifetime_channel_count(session, user_id: int) -> int:
    result = await session.execute(
        select(func.count())
        .select_from(Membership)
        .where(
            Membership.user_id == user_id,
            Membership.validity_days == 9999
        )
    )
    return result.scalar() or 0


def round_price(price: float) -> int:
    price = int(price)
    remainder = price % 100

    if remainder < 50:
        return price - remainder + 99
    else:
        return price - remainder + 199


def calculate_escalated_price(base_price: int, lifetime_count: int) -> int:
    """
    Escalation starts after 3 lifetime purchases
    """
    if lifetime_count < 3:
        return base_price

    price = base_price

    for _ in range(lifetime_count - 2):
        price = round_price(price * 1.20)

    return price


# =========================================================
# USER TIER FOR CHANNEL
# =========================================================

def get_user_tier_for_channel(user, channel_id: int) -> int:

    if user.is_lifetime_member and user.lifetime_amount:
        return calculate_tier_from_amount(user.lifetime_amount)

    if channel_id == 1 and user.channel_1_tier:
        return user.channel_1_tier

    if channel_id > 1:
        return max(user.current_tier, 3)

    return user.current_tier


# =========================================================
# GET PLANS FOR USER
# =========================================================

async def get_plans_for_user(user, channel_id: int, session):

    tier = get_user_tier_for_channel(user, channel_id)

    plans = TIER_PLANS[tier]["plans"]

    # =====================================================
    # LIFETIME MODE
    # =====================================================

    if user.is_lifetime_member:

        lifetime_count = await get_lifetime_channel_count(session, user.id)

        if user.lifetime_amount and user.lifetime_amount > 999:
            base_price = int(user.lifetime_amount)
        else:
            base_price = 999

        price = calculate_escalated_price(base_price, lifetime_count)

        return [{
            "validity": "Lifetime",
            "days": 9999,
            "price": price
        }]

    return plans


# =========================================================
# UPDATE USER TIER
# =========================================================

def update_user_tier(user, amount_paid: int, channel_id: int, is_lifetime=False):

    if amount_paid > user.highest_amount_paid:
        user.highest_amount_paid = amount_paid

    if channel_id == 1 and not user.channel_1_tier:
        user.channel_1_tier = calculate_tier_from_amount(amount_paid)

    if amount_paid >= 299:
        user.current_tier = 4
    elif user.current_tier < 3:
        user.current_tier = max(user.current_tier, calculate_tier_from_amount(amount_paid))

    if is_lifetime:
        user.is_lifetime_member = True
        user.lifetime_amount = amount_paid


# =========================================================
# FORMAT PLAN DISPLAY
# =========================================================

def format_plan_display(plan: dict):

    validity = plan["validity"]
    price = plan["price"]

    labels = {
        "1M": "1 Month",
        "3M": "3 Months",
        "4M": "4 Months",
        "6M": "6 Months",
        "1Y": "1 Year",
    }

    if validity == "Lifetime":
        return f"💎 Lifetime Access — ₹{price}"
    else:
        return f"{labels.get(validity, validity)} — ₹{price}"