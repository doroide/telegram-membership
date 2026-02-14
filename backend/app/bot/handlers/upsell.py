from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select

from backend.app.db.session import async_session
from backend.app.db.models import User, Channel, Membership
from backend.app.services.payment_service import create_payment_link
from backend.bot.bot import bot

router = Router()

# Upsell configuration (can be moved to database later)
UPSELL_CONFIG = {
    30: {  # 1 month buyers
        "to_validity": 90,
        "discount_percent": 15,
        "message": "Upgrade to 3 months and save ₹{savings}!"
    },
    90: {  # 3 month buyers
        "to_validity": 180,
        "discount_percent": 10,
        "message": "Upgrade to 6 months and save ₹{savings}!"
    },
    120: {  # 4 month buyers
        "to_validity": 365,
        "discount_percent": 15,
        "message": "Upgrade to 1 year and save ₹{savings}!"
    },
    180: {  # 6 month buyers
        "to_validity": 365,
        "discount_percent": 12,
        "message": "Upgrade to 1 year and save ₹{savings}!"
    }
}


# =====================================================
# PRICING HELPER
# =====================================================

def get_plan_price(tier: int, validity_days: int) -> int:
    """Get the correct price for a plan based on tier and validity"""
    pricing = {
        # Tier 1 pricing
        1: {30: 49, 90: 149, 120: 199, 180: 299, 365: 599},
        # Tier 2 pricing
        2: {30: 99, 90: 299, 120: 399, 180: 599, 365: 1199},
        # Tier 3 pricing
        3: {30: 199, 90: 599, 120: 799, 180: 1199, 365: 2399},
        # Tier 4 pricing
        4: {30: 299, 90: 899, 120: 1199, 180: 1799, 365: 3599},
    }
    
    if tier not in pricing or validity_days not in pricing[tier]:
        return 0
    
    return pricing[tier][validity_days]


# =====================================================
# OFFER UPSELL AFTER PAYMENT
# =====================================================

async def offer_upsell(user_telegram_id: int, membership_id: int, amount_paid: float):
    """Offer upsell after successful payment"""
    
    print(f"🎁 offer_upsell called: user={user_telegram_id}, membership_id={membership_id}")
    
    try:
        async with async_session() as session:
            membership = await session.get(Membership, membership_id)
            
            if not membership:
                print(f"❌ Membership {membership_id} not found")
                return
            
            # Don't upsell for lifetime or 1-year plans
            if membership.validity_days >= 365:
                print(f"⏭️ Skipping upsell for {membership.validity_days}-day plan")
                return
            
            # Check if upsell available for this plan
            if membership.validity_days not in UPSELL_CONFIG:
                print(f"⏭️ No upsell configured for {membership.validity_days}-day plan")
                return
            
            upsell = UPSELL_CONFIG[membership.validity_days]
            to_validity = upsell["to_validity"]
            discount_percent = upsell["discount_percent"]
            
            user = await session.get(User, membership.user_id)
            channel = await session.get(Channel, membership.channel_id)
            
            if not user or not channel:
                print(f"❌ User or channel not found")
                return
            
            # Calculate prices
            current_price = get_plan_price(user.current_tier, membership.validity_days)
            upgrade_price = get_plan_price(user.current_tier, to_validity)
            discounted_price = int(upgrade_price * (1 - discount_percent / 100))
            savings = upgrade_price - discounted_price
            
            # Calculate what they'd save vs buying current plan multiple times
            months_current = membership.validity_days // 30
            months_upgrade = to_validity // 30
            multi_buy_cost = current_price * (months_upgrade // months_current)
            total_savings = multi_buy_cost - discounted_price
            
            # Display names
            current_display = {30: "1 Month", 90: "3 Months", 120: "4 Months", 180: "6 Months"}.get(membership.validity_days, f"{membership.validity_days} days")
            upgrade_display = {30: "1 Month", 90: "3 Months", 120: "4 Months", 180: "6 Months", 365: "1 Year"}.get(to_validity, f"{to_validity} days")
            
            # Track upsell attempt
            from backend.app.db.models import UpsellAttempt
            upsell_attempt = UpsellAttempt(
                user_id=user.id,
                channel_id=channel.id,
                from_validity_days=membership.validity_days,
                to_validity_days=to_validity,
                from_amount=current_price,
                to_amount=discounted_price,
                discount_amount=savings,
                accepted=False
            )
            session.add(upsell_attempt)
            await session.commit()
            await session.refresh(upsell_attempt)
            
            # Create keyboard
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text=f"🎁 Upgrade to {upgrade_display} - ₹{discounted_price}",
                    callback_data=f"upsell_accept_{upsell_attempt.id}"
                )],
                [InlineKeyboardButton(
                    text="❌ No Thanks",
                    callback_data=f"upsell_decline_{upsell_attempt.id}"
                )]
            ])
            
            # Send upsell offer
            await bot.send_message(
                chat_id=user_telegram_id,
                text=(
                    f"🎁 <b>Special Upgrade Offer!</b>\n\n"
                    f"📺 Channel: <b>{channel.name}</b>\n"
                    f"🎯 You just bought: {current_display} (₹{int(amount_paid)})\n\n"
                    f"<b>Upgrade Now and Save!</b>\n"
                    f"💰 {upgrade_display}: <s>₹{upgrade_price}</s> ₹{discounted_price}\n"
                    f"💎 You save: ₹{total_savings}\n"
                    f"⚡ Discount: {discount_percent}% OFF\n\n"
                    f"This offer expires in 5 minutes!"
                ),
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            
            print(f"✅ Upsell offer sent to user {user_telegram_id}")
            
    except Exception as e:
        print(f"⚠️ Error in offer_upsell: {e}")
        import traceback
        traceback.print_exc()


# =====================================================
# ACCEPT UPSELL
# =====================================================

@router.callback_query(F.data.startswith("upsell_accept_"))
async def accept_upsell(callback: CallbackQuery):
    """User accepted upsell offer"""
    
    upsell_attempt_id = int(callback.data.split("_")[2])
    
    async with async_session() as session:
        from backend.app.db.models import UpsellAttempt
        
        upsell_attempt = await session.get(UpsellAttempt, upsell_attempt_id)
        
        if not upsell_attempt:
            await callback.answer("Offer expired", show_alert=True)
            return
        
        # Mark as accepted
        upsell_attempt.accepted = True
        await session.commit()
        
        # Get user and channel
        user = await session.get(User, upsell_attempt.user_id)
        channel = await session.get(Channel, upsell_attempt.channel_id)
        
        # Create payment link
        try:
            payment_link = create_payment_link(
                user_id=user.id,
                telegram_id=user.telegram_id,
                channel_id=channel.id,
                amount=upsell_attempt.to_amount,
                validity_days=upsell_attempt.to_validity_days
            )
            
            upgrade_display = {30: "1 Month", 90: "3 Months", 120: "4 Months", 180: "6 Months", 365: "1 Year"}.get(upsell_attempt.to_validity_days, f"{upsell_attempt.to_validity_days} days")
            
            await callback.message.edit_text(
                f"🎁 <b>Great Choice!</b>\n\n"
                f"📺 Channel: <b>{channel.name}</b>\n"
                f"⏱️ Plan: {upgrade_display}\n"
                f"💰 Amount: ₹{int(upsell_attempt.to_amount)}\n\n"
                f"👉 Complete payment:\n{payment_link}\n\n"
                f"<i>Link expires in 10 minutes</i>",
                parse_mode="HTML"
            )
            
            await callback.answer("✅ Payment link created!", show_alert=False)
            
            print(f"✅ User {user.telegram_id} accepted upsell: {upsell_attempt.from_validity_days}d → {upsell_attempt.to_validity_days}d")
            
        except Exception as e:
            print(f"❌ Error creating upsell payment link: {e}")
            await callback.answer("Error creating payment link. Please try again.", show_alert=True)


# =====================================================
# DECLINE UPSELL
# =====================================================

@router.callback_query(F.data.startswith("upsell_decline_"))
async def decline_upsell(callback: CallbackQuery):
    """User declined upsell offer"""
    
    upsell_attempt_id = int(callback.data.split("_")[2])
    
    async with async_session() as session:
        from backend.app.db.models import UpsellAttempt
        
        upsell_attempt = await session.get(UpsellAttempt, upsell_attempt_id)
        
        if upsell_attempt:
            # Already marked as accepted=False by default
            print(f"✅ User declined upsell: {upsell_attempt.from_validity_days}d → {upsell_attempt.to_validity_days}d")
    
    await callback.message.edit_text(
        "👍 <b>No problem!</b>\n\n"
        "Enjoy your subscription!\n"
        "You can upgrade anytime from /myplans",
        parse_mode="HTML"
    )
    
    await callback.answer()