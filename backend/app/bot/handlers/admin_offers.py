"""
Admin Offers Handler - Create manual offers for users
Add to backend/app/bot/handlers/admin_offers.py
"""
import os
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select
from backend.app.db.session import async_session
from backend.app.db.models import User, Channel, UpsellAttempt
import logging

router = Router()
logger = logging.getLogger(__name__)

ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID"))


class OfferStates(StatesGroup):
    waiting_for_recipients = State()
    waiting_for_channel = State()
    waiting_for_details = State()


@router.callback_query(F.data == "admin_give_offers")
async def admin_give_offers(callback: CallbackQuery):
    """Admin: Give Offers button"""
    await callback.answer()
    
    if callback.from_user.id != ADMIN_USER_ID:
        await callback.answer("⛔ Admin only", show_alert=True)
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Specific User IDs", callback_data="offer_users")],
        [InlineKeyboardButton(text="📺 All Users of Channel", callback_data="offer_channel")],
        [InlineKeyboardButton(text="🌐 All Users", callback_data="offer_all")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="admin_panel")]
    ])
    
    await callback.message.edit_text(
        "🎁 <b>Give Manual Offers</b>\n\n"
        "Select recipients:",
        parse_mode="HTML",
        reply_markup=keyboard
    )


@router.callback_query(F.data == "offer_users")
async def offer_to_users(callback: CallbackQuery, state: FSMContext):
    """Offer to specific user IDs"""
    await callback.answer()
    
    await callback.message.edit_text(
        "👤 <b>Send Offer to Specific Users</b>\n\n"
        "Enter user IDs (comma-separated):\n"
        "Example: 952763698, 123456789, 987654321\n\n"
        "Or type /cancel to go back",
        parse_mode="HTML"
    )
    
    await state.set_state(OfferStates.waiting_for_recipients)


@router.callback_query(F.data == "offer_channel")
async def offer_to_channel(callback: CallbackQuery, state: FSMContext):
    """Offer to all users of a channel"""
    await callback.answer()
    
    async with async_session() as db:
        result = await db.execute(select(Channel).where(Channel.is_active == True))
        channels = result.scalars().all()
        
        keyboard = []
        for ch in channels:
            keyboard.append([
                InlineKeyboardButton(text=ch.name, callback_data=f"offer_ch_{ch.id}")
            ])
        keyboard.append([InlineKeyboardButton(text="🔙 Back", callback_data="admin_give_offers")])
        
        await callback.message.edit_text(
            "📺 <b>Select Channel</b>\n\n"
            "Offer will be sent to all users who have/had this channel:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
        )


@router.callback_query(F.data.startswith("offer_ch_"))
async def channel_selected(callback: CallbackQuery, state: FSMContext):
    """Channel selected"""
    channel_id = int(callback.data.split("_")[2])
    await state.update_data(channel_filter=channel_id)
    await callback.answer()
    await ask_offer_details(callback.message, state)


@router.callback_query(F.data == "offer_all")
async def offer_to_all(callback: CallbackQuery, state: FSMContext):
    """Offer to ALL users"""
    await callback.answer()
    await state.update_data(send_to_all=True)
    await ask_offer_details(callback.message, state)


async def ask_offer_details(message: Message, state: FSMContext):
    """Ask for offer details"""
    await message.edit_text(
        "💰 <b>Offer Details</b>\n\n"
        "Enter offer in this format:\n\n"
        "<code>channel_id, from_days, to_days, discount_percent, message</code>\n\n"
        "<b>Example:</b>\n"
        "<code>11, 30, 90, 50, Get 50% off upgrade!</code>\n\n"
        "This creates:\n"
        "• Channel ID 11 (Adult Webseries)\n"
        "• Upgrade from 1 month to 3 months\n"
        "• 50% discount\n"
        "• Custom message\n\n"
        "Or /cancel to abort",
        parse_mode="HTML"
    )
    await state.set_state(OfferStates.waiting_for_details)


@router.message(OfferStates.waiting_for_recipients)
async def process_user_ids(message: Message, state: FSMContext):
    """Process user IDs"""
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Cancelled")
        return
    
    try:
        user_ids = [int(x.strip()) for x in message.text.split(",")]
        await state.update_data(user_ids=user_ids)
        await ask_offer_details(message, state)
    except:
        await message.answer("❌ Invalid format. Use: 123456, 789012, 345678")


@router.message(OfferStates.waiting_for_details)
async def process_offer_details(message: Message, state: FSMContext):
    """Process and create offers"""
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Cancelled")
        return
    
    try:
        parts = [x.strip() for x in message.text.split(",")]
        channel_id = int(parts[0])
        from_days = int(parts[1])
        to_days = int(parts[2])
        discount_pct = int(parts[3])
        custom_msg = parts[4] if len(parts) > 4 else "Special offer from admin!"
        
        data = await state.get_data()
        
        # Calculate pricing
        base_prices = {
            1: {30: 49, 90: 149, 180: 299, 365: 599},
            2: {30: 99, 90: 299, 180: 599, 365: 1199},
            3: {30: 199, 90: 599, 180: 1199, 365: 2399},
            4: {30: 299, 90: 899, 180: 1799, 365: 3599},
        }
        
        async with async_session() as db:
            # Get recipients
            if data.get("send_to_all"):
                result = await db.execute(select(User))
                users = result.scalars().all()
            elif data.get("channel_filter"):
                # Users who have this channel
                from backend.app.db.models import Membership
                result = await db.execute(
                    select(User).join(Membership).where(Membership.channel_id == data["channel_filter"]).distinct()
                )
                users = result.scalars().all()
            else:
                # Specific user IDs
                result = await db.execute(
                    select(User).where(User.telegram_id.in_(data["user_ids"]))
                )
                users = result.scalars().all()
            
            # Create offers
            created = 0
            for user in users:
                tier = user.current_tier
                from_price = base_prices.get(tier, base_prices[3])[from_days]
                to_price_orig = base_prices.get(tier, base_prices[3])[to_days]
                discount_amt = to_price_orig * (discount_pct / 100)
                to_price = to_price_orig - discount_amt
                
                offer = UpsellAttempt(
                    user_id=user.id,
                    channel_id=channel_id,
                    from_validity_days=from_days,
                    to_validity_days=to_days,
                    from_amount=from_price,
                    to_amount=to_price,
                    discount_amount=discount_amt,
                    is_manual=True,
                    created_by_admin=ADMIN_USER_ID,
                    custom_message=custom_msg,
                    accepted=False
                )
                db.add(offer)
                created += 1
            
            await db.commit()
            
            await message.answer(
                f"✅ <b>Offers Created!</b>\n\n"
                f"👥 Sent to: {created} users\n"
                f"📺 Channel: {channel_id}\n"
                f"💰 Discount: {discount_pct}%\n\n"
                f"Users will see it in 'Offers for You'",
                parse_mode="HTML"
            )
            
        await state.clear()
        
    except Exception as e:
        logger.error(f"Error creating offers: {e}")
        await message.answer(f"❌ Error: {e}\n\nPlease try again")


@router.message(Command("cancel"))
async def cancel_handler(message: Message, state: FSMContext):
    """Cancel current operation"""
    await state.clear()
    await message.answer("❌ Operation cancelled")