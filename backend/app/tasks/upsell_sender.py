"""
Scheduled Upsell Sender - Runs daily, sends upsell offers on Day 5 after purchase
Add this to backend/app/tasks/upsell_sender.py
"""

from datetime import datetime, timedelta, timezone
from sqlalchemy import select, and_
from backend.app.db.session import async_session
from backend.app.db.models import Membership, User, Channel, UpsellAttempt
from backend.bot.bot import bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import asyncio
import logging

logger = logging.getLogger(__name__)

# Upsell mapping with 20% discount
UPSELL_MAP = {
    30: {"to_days": 90, "from_price": 49, "to_price": 119, "discount_pct": 20},    # 1M → 3M (Tier 1)
    90: {"to_days": 180, "from_price": 149, "to_price": 239, "discount_pct": 20},  # 3M → 6M
    120: {"to_days": 365, "from_price": 199, "to_price": 479, "discount_pct": 20}, # 4M → 1Y
    180: {"to_days": 365, "from_price": 299, "to_price": 479, "discount_pct": 20}, # 6M → 1Y
}


def calculate_upsell_price(tier: int, from_days: int, to_days: int) -> dict:
    """Calculate upsell price with 20% discount"""
    base_prices = {
        1: {30: 49, 90: 149, 120: 199, 180: 299, 365: 599},
        2: {30: 99, 90: 299, 120: 399, 180: 599, 365: 1199},
        3: {30: 199, 90: 599, 120: 799, 180: 1199, 365: 2399},
        4: {30: 299, 90: 899, 120: 1199, 180: 1799, 365: 3599},
    }
    
    from_price = base_prices[tier][from_days]
    to_price_original = base_prices[tier][to_days]
    
    # Apply 20% discount
    discount_amount = to_price_original * 0.20
    to_price_discounted = to_price_original - discount_amount
    
    return {
        "from_price": from_price,
        "to_price": to_price_discounted,
        "original_price": to_price_original,
        "discount_amount": discount_amount,
        "discount_pct": 20
    }


async def send_upsell_offers():
    """
    Run daily - Find memberships that are exactly 5 days old
    Send upsell offers if applicable
    """
    async with async_session() as db:
        # Calculate date 5 days ago
        five_days_ago = datetime.now(timezone.utc) - timedelta(days=5)
        five_days_start = five_days_ago.replace(hour=0, minute=0, second=0, microsecond=0)
        five_days_end = five_days_ago.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        # Find memberships created exactly 5 days ago
        result = await db.execute(
            select(Membership).where(
                and_(
                    Membership.created_at >= five_days_start,
                    Membership.created_at <= five_days_end,
                    Membership.is_active == True
                )
            )
        )
        memberships = result.scalars().all()
        
        logger.info(f"Found {len(memberships)} memberships from 5 days ago")
        
        for membership in memberships:
            try:
                # Check if already sent upsell for this membership
                existing = await db.execute(
                    select(UpsellAttempt).where(
                        and_(
                            UpsellAttempt.user_id == membership.user_id,
                            UpsellAttempt.channel_id == membership.channel_id,
                            UpsellAttempt.from_validity_days == membership.validity_days
                        )
                    )
                )
                if existing.scalar_one_or_none():
                    continue  # Already sent
                
                # Check if upsell is available for this plan
                if membership.validity_days not in UPSELL_MAP:
                    continue  # No upsell for this duration
                
                # Skip if lifetime or 1-year plan
                if membership.validity_days >= 365:
                    continue
                
                # Get user and channel
                user = await db.get(User, membership.user_id)
                channel = await db.get(Channel, membership.channel_id)
                
                # Calculate upsell pricing
                upsell_info = UPSELL_MAP[membership.validity_days]
                pricing = calculate_upsell_price(
                    membership.tier,
                    membership.validity_days,
                    upsell_info["to_days"]
                )
                
                # Create upsell attempt record
                upsell_attempt = UpsellAttempt(
                    user_id=membership.user_id,
                    channel_id=membership.channel_id,
                    from_validity_days=membership.validity_days,
                    to_validity_days=upsell_info["to_days"],
                    from_amount=pricing["from_price"],
                    to_amount=pricing["to_price"],
                    discount_amount=pricing["discount_amount"],
                    accepted=False
                )
                db.add(upsell_attempt)
                await db.commit()
                
                # Send upsell message
                duration_map = {30: "1 month", 90: "3 months", 120: "4 months", 180: "6 months", 365: "1 year"}
                from_duration = duration_map.get(membership.validity_days, f"{membership.validity_days} days")
                to_duration = duration_map.get(upsell_info["to_days"], f"{upsell_info['to_days']} days")
                
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(
                        text=f"🎁 Upgrade to {to_duration.title()}",
                        callback_data=f"upsell_accept_{upsell_attempt.id}"
                    )],
                    [InlineKeyboardButton(text="❌ No Thanks", callback_data=f"upsell_decline_{upsell_attempt.id}")]
                ])
                
                await bot.send_message(
                    user.telegram_id,
                    f"🎁 <b>Special Upgrade Offer!</b>\n\n"
                    f"You're enjoying <b>{channel.name}</b>!\n\n"
                    f"<b>Upgrade Now:</b>\n"
                    f"From: {from_duration} → {to_duration}\n\n"
                    f"💰 Original Price: ₹{pricing['original_price']:.0f}\n"
                    f"🎉 Your Price: ₹{pricing['to_price']:.0f}\n"
                    f"💸 You Save: ₹{pricing['discount_amount']:.0f} (20% OFF)\n\n"
                    f"✨ Limited time offer!",
                    parse_mode="HTML",
                    reply_markup=keyboard
                )
                
                logger.info(f"Sent upsell offer to user {user.telegram_id} for channel {channel.name}")
                await asyncio.sleep(1)  # Rate limiting
                
            except Exception as e:
                logger.error(f"Error sending upsell for membership {membership.id}: {e}")
                continue


# Add this to your cron job or scheduler
# Run once daily at 10 AM
async def scheduled_upsell_task():
    """Background task to send upsell offers daily"""
    while True:
        try:
            await send_upsell_offers()
        except Exception as e:
            logger.error(f"Scheduled upsell task error: {e}")
        
        # Run once per day (24 hours)
        await asyncio.sleep(86400)