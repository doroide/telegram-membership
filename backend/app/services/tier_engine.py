# =========================================================
# SYSTEM 1 - TIER ENGINE
# =========================================================

from sqlalchemy import select, func
from backend.app.db.models import Membership

# =========================================================
# TIER PRICING CONFIGURATION
#
# Tier 1:          highest_amount_paid ₹49–₹98
# Tier 2:          highest_amount_paid ₹99–₹698  (Tier 1 upgraded + Tier 2 same prices)
# Tier 3:          new user (₹0) OR highest_amount_paid ₹699+
# Lifetime mode:   user bought any lifetime plan
# =========================================================

TIER_PLANS = {
    1: {
        "name": "Tier 1",
        "plans": [
            {"validity": "1M",       "days": 30,   "price": 49},
            {"validity": "3M",       "days": 90,   "price": 99},
            {"validity": "6M",       "days": 180,  "price": 199},
            {"validity": "1Y",       "days": 365,  "price": 399},
            {"validity": "Lifetime", "days": 9999, "price": 799},
        ],
    },
    2: {
        "name": "Tier 2",
        "plans": [
            {"validity": "1M",       "days": 30,   "price": 99},
            {"validity": "3M",       "days": 90,   "price": 199},
            {"validity": "6M",       "days": 180,  "price": 399},
            {"validity": "1Y",       "days": 365,  "price": 699},
            {"validity": "Lifetime", "days": 9999, "price": 999},
        ],
    },
    3: {
        "name": "Tier 3",
        "plans": [
            {"validity": "1M",       "days": 30,   "price": 199},
            {"validity": "3M",       "days": 90,   "price": 399},
            {"validity": "6M",       "days": 180,  "price": 599},
            {"validity": "1Y",       "days": 365,  "price": 799},
            {"validity": "Lifetime", "days": 9999, "price": 999},
        ],
    },
}


# =========================================================
# TIER CALCULATION FROM AMOUNT
#
# ₹0          → Tier 3 (new user default)
# ₹49 – ₹98  → Tier 1
# ₹99 – ₹698 → Tier 2  (Tier 1 upgraded & Tier 2 share same plans)
# ₹699+       → Tier 3
# =========================================================

def calculate_tier_from_amount(amount: int) -> int:
    if amount == 0:
        return 3  # new user default
    elif amount < 99:
        return 1  # ₹49–₹98
    elif amount < 699:
        return 2  # ₹99–₹698
    else:
        return 3  # ₹699+


def get_price_for_validity(tier: int, validity_days: int):
    """Get price for a specific tier and validity days"""
    plans = TIER_PLANS.get(tier, {}).get("plans", [])
    for plan in plans:
        if plan["days"] == validity_days:
            return plan["price"]
    return None


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
    Escalation starts after 3 lifetime purchases.
    Always escalates from ₹999 base even if first lifetime was ₹799.
    Admin lifetime (>₹999) escalates from that amount.
    """
    if lifetime_count < 3:
        return base_price

    # Always escalate from ₹999 minimum
    escalation_base = max(base_price, 999)
    price = escalation_base

    for _ in range(lifetime_count - 2):
        price = round_price(price * 1.20)

    return price


# =========================================================
# GET USER TIER FOR CHANNEL
# =========================================================

def get_user_tier_for_channel(user, channel_id: int) -> int:
    """
    Determine which tier plans to show for a user on a given channel.
    Tier is based purely on highest_amount_paid — no channel minimum enforced.
    """
    highest = int(user.highest_amount_paid or 0)
    return calculate_tier_from_amount(highest)


# =========================================================
# GET PLANS FOR USER
# =========================================================

async def get_plans_for_user(user, channel_id: int, session=None):
    """
    Returns list of plans to show user for a channel.

    Lifetime mode: user sees only lifetime plan (escalated price).
    Normal mode:   user sees plans based on their tier.
    """

    # ── LIFETIME MODE ──────────────────────────────────────
    if user.is_lifetime_member:
        lifetime_count = 0
        if session:
            lifetime_count = await get_lifetime_channel_count(session, user.id)

        # Admin lifetime base price (>₹999), else default ₹999
        if user.lifetime_amount and int(user.lifetime_amount) > 999:
            base_price = int(user.lifetime_amount)
        else:
            base_price = 999

        price = calculate_escalated_price(base_price, lifetime_count)

        return [{
            "validity": "Lifetime",
            "days": 9999,
            "price": price
        }]

    # ── NORMAL MODE ────────────────────────────────────────
    tier = get_user_tier_for_channel(user, channel_id)
    return TIER_PLANS[tier]["plans"]


# =========================================================
# UPDATE USER TIER
# =========================================================

def update_user_tier(user, amount_paid: int, channel_id: int, is_lifetime=False):
    """Update user tier fields after a payment."""

    if amount_paid > int(user.highest_amount_paid or 0):
        user.highest_amount_paid = amount_paid

    user.current_tier = calculate_tier_from_amount(amount_paid)

    if is_lifetime:
        user.is_lifetime_member = True
        user.lifetime_amount = amount_paid


# =========================================================
# FORMAT PLAN DISPLAY
# =========================================================

def format_plan_display(plan: dict) -> str:
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