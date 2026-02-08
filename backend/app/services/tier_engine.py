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
            {"validity": "Lifetime", "days": 730, "price": 999},
        ]
    },
    2: {
        "name": "Tier 2 (Standard)",
        "plans": [
            {"validity": "1M", "days": 30, "price": 99},
            {"validity": "4M", "days": 120, "price": 299},
            {"validity": "6M", "days": 180, "price": 499},
            {"validity": "1Y", "days": 365, "price": 799},
            {"validity": "Lifetime", "days": 730, "price": 999},
        ]
    },
    3: {
        "name": "Tier 3 (Premium)",
        "plans": [
            {"validity": "1M", "days": 30, "price": 199},
            {"validity": "3M", "days": 90, "price": 399},
            {"validity": "6M", "days": 180, "price": 599},
            {"validity": "1Y", "days": 365, "price": 799},
            {"validity": "Lifetime", "days": 730, "price": 999},
        ]
    },
    4: {
        "name": "Tier 4 (Elite)",
        "plans": [
            {"validity": "1M", "days": 30, "price": 299},
            {"validity": "3M", "days": 90, "price": 599},
            {"validity": "6M", "days": 180, "price": 899},
            {"validity": "1Y", "days": 365, "price": 1199},
            {"validity": "Lifetime", "days": 730, "price": 1499},
        ]
    }
}


# =========================================================
# TIER CALCULATION FUNCTIONS
# =========================================================

def calculate_tier_from_amount(amount: int) -> int:
    """
    Determine tier based on amount paid
    Returns tier number (1-4)
    """
    if amount >= 299:
        return 4
    elif amount >= 199:
        return 3
    elif amount >= 99:
        return 2
    else:
        return 1


def get_user_tier_for_channel(user, channel_id: int) -> int:
    """
    Get the appropriate tier for a user viewing a specific channel
    
    Rules:
    - Channel 1: Uses channel_1_tier if set, else current_tier
    - Channels 2-10: Minimum Tier 3, unless user has Tier 4
    - Lifetime members: See only lifetime plans at their lifetime_amount tier
    """
    # If user is lifetime member, return tier based on lifetime amount
    if user.is_lifetime_member and user.lifetime_amount:
        return calculate_tier_from_amount(user.lifetime_amount)
    
    # Channel 1 special logic
    if channel_id == 1 and user.channel_1_tier:
        return user.channel_1_tier
    
    # Channels 2-10: Minimum Tier 3
    if channel_id > 1:
        return max(user.current_tier, 3)
    
    # Default to current tier
    return user.current_tier


def get_plans_for_user(user, channel_id: int, lifetime_only: bool = False):
    """
    Get available plans for a user based on their tier
    
    Args:
        user: User object
        channel_id: Channel ID (1-10)
        lifetime_only: If True, return only lifetime plans
    
    Returns:
        List of plan dictionaries with validity, days, price
    """
    tier = get_user_tier_for_channel(user, channel_id)
    
    plans = TIER_PLANS[tier]["plans"]
    
    # If user is lifetime member, show only lifetime plans
    if user.is_lifetime_member or lifetime_only:
        return [p for p in plans if p["validity"] == "Lifetime"]
    
    return plans


def update_user_tier(user, amount_paid: int, channel_id: int, is_lifetime: bool = False):
    """
    Update user's tier based on new payment
    
    Rules:
    - Track highest amount paid
    - Channel 1 first purchase locks channel_1_tier
    - Any payment >= 299 upgrades to Tier 4
    - Lifetime purchases set is_lifetime_member = True
    """
    # Update highest amount
    if amount_paid > user.highest_amount_paid:
        user.highest_amount_paid = amount_paid
    
    # Lock Channel 1 tier on first purchase
    if channel_id == 1 and not user.channel_1_tier:
        user.channel_1_tier = calculate_tier_from_amount(amount_paid)
    
    # Upgrade to Tier 4 if payment >= 299
    if amount_paid >= 299:
        user.current_tier = 4
    elif user.current_tier < 3:
        # Ensure minimum Tier 3 for non-Channel-1 purchases
        user.current_tier = max(user.current_tier, calculate_tier_from_amount(amount_paid))
    
    # Handle lifetime membership
    if is_lifetime:
        user.is_lifetime_member = True
        user.lifetime_amount = amount_paid


def get_price_for_validity(tier: int, validity_days: int) -> int:
    """
    Get price for a specific tier and validity
    
    Args:
        tier: Tier number (1-4)
        validity_days: Number of days (30, 90, 120, 180, 365, 730)
    
    Returns:
        Price in rupees, or None if not found
    """
    plans = TIER_PLANS.get(tier, {}).get("plans", [])
    
    for plan in plans:
        if plan["days"] == validity_days:
            return plan["price"]
    
    return None


def format_plan_display(plan: dict) -> str:
    """
    Format plan for display in bot
    
    Args:
        plan: Plan dictionary with validity, days, price
    
    Returns:
        Formatted string like "1 Month ₹49" or "Lifetime ₹999"
    """
    validity = plan["validity"]
    price = plan["price"]
    
    if validity == "Lifetime":
        return f"Lifetime ₹{price}"
    else:
        return f"{validity} ₹{price}"