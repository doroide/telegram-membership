from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select
from backend.app.db.session import async_session
from backend.app.db.models import User, Channel
from backend.app.services.payment_service import create_payment_link

router = Router()

# =====================================================
# PLAN SLABS
# =====================================================
PLAN_SLABS = {
    "A": [
        ("1 Month ₹49", 30, 49),
        ("4 Months ₹199", 120, 199),
        ("6 Months ₹299", 180, 299),
        ("12 Months ₹599", 365, 599),
        ("Lifetime ₹999", 730, 999),
    ],
    "B": [
        ("1 Month ₹99", 30, 99),
        ("4 Months ₹299", 120, 299),
        ("6 Months ₹599", 180, 599),
        ("12 Months ₹799", 365, 799),
        ("Lifetime ₹999", 730, 999),
    ],
    "C": [
        ("1 Month ₹199", 30, 199),
        ("3 Months ₹399", 90, 399),
        ("6 Months ₹599", 180, 599),
        ("12 Months ₹799", 365, 799),
        ("Lifetime ₹999", 730, 999),
    ],
}

# =====================================================
# CHANNEL CLICK → SHOW PLANS
# callback: userch_5
# =====================================================
@router.callback_query(F.data.startswith("userch_"))
async def show_plans(callback: CallbackQuery):
    print("CHANNEL CLICK:", callback.data)
    
    try:
        channel_id = int(callback.data.split("_")[1])
    except (IndexError, ValueError):
        await callback.answer("Invalid channel ❌", show_alert=True)
        return
    
    async with async_session() as session:
        user = await session.scalar(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        channel = await session.get(Channel, channel_id)
    
    if not channel:
        await callback.answer("Channel not found ❌", show_alert=True)
        return
    
    slab = user.plan_slab or "A"
    plans = PLAN_SLABS.get(slab, PLAN_SLABS["A"])
    
    buttons = []
    for i, (text, days, price) in enumerate(plans):
        buttons.append([
            InlineKeyboardButton(
                text=text,
                callback_data=f"buy_{channel_id}_{i}"
            )
        ])
    
    await callback.message.edit_text(
        f"💳 <b>{channel.name}</b>\n\nChoose your plan:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML"
    )
    await callback.answer()

# =====================================================
# BUY PLAN
# callback: buy_5_2
# =====================================================
@router.callback_query(F.data.startswith("buy_"))
async def buy_plan(callback: CallbackQuery):
    print("BUY CALLBACK:", callback.data)
    
    try:
        parts = callback.data.split("_")
        channel_id = int(parts[1])
        index = int(parts[2])
    except (IndexError, ValueError):
        print("ERROR: Invalid callback format")
        await callback.answer("Invalid plan ❌", show_alert=True)
        return
    
    async with async_session() as session:
        user = await session.scalar(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        channel = await session.get(Channel, channel_id)
    
    if not user or not channel:
        await callback.answer("Error: User or channel not found ❌", show_alert=True)
        return
    
    slab = user.plan_slab or "A"
    
    # Validate index
    if index >= len(PLAN_SLABS[slab]):
        print(f"ERROR: Index {index} out of range for slab {slab}")
        await callback.answer("Invalid plan ❌", show_alert=True)
        return
    
    text, days, price = PLAN_SLABS[slab][index]
    
    print(f"Creating payment: user={user.telegram_id}, channel={channel_id}, days={days}, price={price}")
    
    try:
        payment_link = await create_payment_link(
            user_id=callback.from_user.id,
            channel_id=channel_id,
            days=days,
            price=price
        )
    except Exception as e:
        print(f"ERROR creating payment link: {e}")
        await callback.answer("Error creating payment link ❌", show_alert=True)
        return
    
    await callback.message.answer(
        f"💳 <b>{text}</b>\n"
        f"📢 Channel: <b>{channel.name}</b>\n\n"
        f"💰 Amount: ₹{price}\n"
        f"⏰ Duration: {days} days\n\n"
        f"Click here to pay:\n{payment_link}\n\n"
        f"✅ After successful payment, you will receive access automatically!"
    )
    await callback.answer()