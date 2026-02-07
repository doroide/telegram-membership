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

    raw = callback.data.strip()
    print("CHANNEL CLICK:", repr(raw))

    parts = raw.split("_")

    if len(parts) != 2:
        await callback.answer("Invalid channel ❌", show_alert=True)
        return

    _, channel_id = parts
    channel_id = int(channel_id)

    async with async_session() as session:
        user = await session.scalar(
            select(User).where(User.telegram_id == callback.from_user.id)
        )

        channel = await session.get(Channel, channel_id)

    if not user or not channel:
        await callback.answer("Channel not found ❌", show_alert=True)
        return

    slab = user.plan_slab or "A"
    plans = PLAN_SLABS.get(slab, PLAN_SLABS["A"])

    buttons = []

    for i, (text, days, price) in enumerate(plans):
        buttons.append([
            InlineKeyboardButton(
                text=text,
                callback_data=f"buy_{channel_id}_{i}"  # safe index
            )
        ])

    await callback.message.edit_text(
        f"💳 <b>{channel.name}</b>\n\nChoose your plan:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )


# =====================================================
# BUY PLAN
# callback: buy_5_2
# =====================================================

@router.callback_query(F.data.startswith("buy_"))
async def buy_plan(callback: CallbackQuery):

    raw = callback.data.strip()
    print("BUY CLICK:", repr(raw))

    parts = raw.split("_")

    # Safety check
    if len(parts) != 3:
        await callback.answer("Invalid plan ❌", show_alert=True)
        return

    _, channel_id, index = parts

    try:
        channel_id = int(channel_id)
        index = int(index)
    except ValueError:
        await callback.answer("Invalid plan ❌", show_alert=True)
        return

    async with async_session() as session:
        user = await session.scalar(
            select(User).where(User.telegram_id == callback.from_user.id)
        )

    if not user:
        await callback.answer("User not found ❌", show_alert=True)
        return

    slab = user.plan_slab or "A"
    plans = PLAN_SLABS.get(slab, PLAN_SLABS["A"])

    # Prevent index crash
    if index < 0 or index >= len(plans):
        await callback.answer("Invalid plan ❌", show_alert=True)
        return

    text, days, price = plans[index]

    payment_link = await create_payment_link(
        user_id=callback.from_user.id,
        channel_id=channel_id,
        days=days,
        price=price
    )

    await callback.message.answer(
        f"💳 <b>{text}</b>\n\n"
        f"Pay here:\n{payment_link}\n\n"
        f"After payment you will receive access automatically ✅"
    )

    await callback.answer()
