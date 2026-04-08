"""
Updated upsell.py - Handle upsell accept/decline with 20% discount
Replace backend/app/bot/handlers/upsell.py
"""

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select
from datetime import datetime, timezone
from backend.app.db.session import async_session
from backend.app.db.models import UpsellAttempt, User, Channel, Membership
import logging

router = Router()
logger = logging.getLogger(__name__)


@router.callback_query(F.data.startswith("upsell_accept_"))
async def handle_upsell_accept(callback: CallbackQuery, state: FSMContext):
    """User accepts upsell offer - route to UPI payment"""
    await callback.answer()
    
    try:
        upsell_id = int(callback.data.split("_")[2])
        
        async with async_session() as db:
            upsell = await db.get(UpsellAttempt, upsell_id)
            if not upsell or upsell.accepted:
                await callback.message.answer("❌ This offer has already been used or expired.")
                return
            
            user = await db.get(User, upsell.user_id)
            channel = await db.get(Channel, upsell.channel_id)

            duration_map = {30: "1 Month", 90: "3 Months", 120: "4 Months", 180: "6 Months", 365: "1 Year"}
            to_duration = duration_map.get(upsell.to_validity_days, f"{upsell.to_validity_days} days")

            # ── Razorpay (disabled — kept for future use) ──────────────
            # import razorpay
            # import os
            #
            # razorpay_client = razorpay.Client(
            #     auth=(os.getenv("RAZORPAY_KEY"), os.getenv("RAZORPAY_SECRET"))
            # )
            #
            # payment_data = {
            #     "amount": int(float(upsell.to_amount) * 100),
            #     "currency": "INR",
            #     "description": f"Upgrade: {channel.name} - {to_duration}",
            #     "customer": {
            #         "name": user.full_name or "User",
            #         "contact": str(user.telegram_id)
            #     },
            #     "notify": {
            #         "sms": False,
            #         "email": False
            #     },
            #     "reminder_enable": False,
            #     "notes": {
            #         "telegram_id": str(user.telegram_id),
            #         "channel_id": str(channel.id),
            #         "validity_days": str(upsell.to_validity_days),
            #         "tier": str(user.current_tier),
            #         "upsell_id": str(upsell.id),
            #         "is_upsell": "true"
            #     }
            # }
            #
            # response = razorpay_client.payment_link.create(payment_data)
            # payment_link = response["short_url"]
            #
            # original_price = float(upsell.to_amount) / 0.8
            #
            # keyboard = InlineKeyboardMarkup(inline_keyboard=[
            #     [InlineKeyboardButton(text="💳 Pay Now", url=payment_link)],
            #     [InlineKeyboardButton(text="📞 Contact Admin", url="https://t.me/Doroide47")]
            # ])
            #
            # await callback.message.edit_text(
            #     f"🎁 <b>Upgrade to {to_duration}</b>\n\n"
            #     f"📺 Channel: {channel.name}\n\n"
            #     f"💰 Original Price: ₹{original_price:.0f}\n"
            #     f"🎉 Your Price: ₹{float(upsell.to_amount):.0f}\n"
            #     f"💸 You Save: ₹{float(upsell.discount_amount):.0f} (20% OFF)\n\n"
            #     f"Click 'Pay Now' to upgrade!\n\n"
            #     f"⚠️ Offer valid for 24 hours",
            #     parse_mode="HTML",
            #     reply_markup=keyboard
            # )
            # ── End Razorpay ───────────────────────────────────────────

            # ── Active: UPI payment flow ───────────────────────────────
            from backend.app.bot.handlers.upi_payment import show_upi_payment
            await show_upi_payment(
                callback=callback,
                channel_id=channel.id,
                days=upsell.to_validity_days,
                price=int(float(upsell.to_amount)),
                channel_name=channel.name,
                state=state
            )

            logger.info(f"User {user.telegram_id} accepted upsell offer {upsell_id}")
    
    except Exception as e:
        logger.error(f"Error handling upsell accept: {e}")
        await callback.message.answer("❌ Something went wrong. Please contact admin.")


@router.callback_query(F.data.startswith("upsell_decline_"))
async def handle_upsell_decline(callback: CallbackQuery):
    """User declines upsell offer"""
    await callback.answer("No problem! You can always upgrade later from /myplans")
    
    try:
        upsell_id = int(callback.data.split("_")[2])
        
        async with async_session() as db:
            upsell = await db.get(UpsellAttempt, upsell_id)
            if upsell:
                await db.commit()
        
        await callback.message.edit_text(
            "👍 No problem!\n\n"
            "You can view all offers anytime from:\n"
            "/myplans → 🎁 Offers for You\n\n"
            "Happy streaming! 🎬"
        )
        
        logger.info(f"User declined upsell offer {upsell_id}")
    
    except Exception as e:
        logger.error(f"Error handling upsell decline: {e}")


async def mark_upsell_completed(upsell_id: int):
    """Mark upsell as accepted after successful payment"""
    async with async_session() as db:
        upsell = await db.get(UpsellAttempt, upsell_id)
        if upsell:
            upsell.accepted = True
            await db.commit()
            logger.info(f"Marked upsell {upsell_id} as completed")