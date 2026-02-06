from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select

from backend.app.db.session import async_session
from backend.app.db.models import User, Channel
from backend.app.services.payment_service import create_payment_link


router = Router()


# =====================================================
# PLAN DEFINITIONS (clean id based)
# =====================================================

PLAN_SLABS = {
    "A": {
        "p1": ("1M ₹49", 30, 49),
        "p2": ("4M ₹199", 120, 199),
        "p3": ("6M ₹299", 180, 299),
        "p4": ("12M ₹599", 365, 599),
        "p5": ("Lifetime ₹999", 730, 999),
    },
    "B": {
        "p1": ("1M ₹99", 30, 99),
        "p2": ("4M ₹299", 120, 299),
        "p3": ("6M ₹599", 180, 599),
        "p4": ("12M ₹799", 365, 799),
        "p5": ("Lifetime ₹999", 730, 999),
    },
    "C": {
        "p1": ("1M ₹199", 30, 199),
        "p2": ("3M ₹399", 90, 399),
        "p3": ("6M ₹599", 180, 599),
        "p4": ("12M ₹799", 365, 799),
        "p5": ("Lifetime ₹999", 730, 999),
    },
}


# =====================================================
# USER CLICKED CHANNEL → SHOW PLANS
# =====================================================

@router.callback_query(F.data.startswith("userch_"))
async def show_plans(callback: CallbackQuery):

    telegram_id = callback.from_user.id
    channel_id = int(callback.data.split("_")[1])

    async with async_session() as session:

        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar()

        if not user:
            await callback.answer("Contact admin first ❌", show_alert=True)
            return

        slab = user.plan_slab or "A"
        channel = await session.get(Channel, channel_id)

    plans = PLAN_SLABS.get(slab, PLAN_SLABS["A"])

    buttons = []

    for plan_key, (label, days, price) in plans.items():
        buttons.append([
            InlineKeyboardButton(
                text=label,
                callback_data=f"buy_{channel_id}_{plan_key}"
            )
        ])

    kb = InlineKeyboardMarkup(inline_keyboard=buttons)

    await callback.message.edit_text(
        f"💳 <b>{channel.name}</b>\n\nChoose your plan:",
        reply_markup=kb
    )


# =====================================================
# USER CLICKED BUY PLAN (SAFE VERSION)
# =====================================================

@router.callback_query(F.data.startswith("buy_"))
async def buy_plan(callback: CallbackQuery):

    try:
        _, channel_id, plan_key = callback.data.split("_")

        channel_id = int(channel_id)

        async with async_session() as session:
            result = await session.execute(
                select(User).where(User.telegram_id == callback.from_user.id)
            )
            user = result.scalar()

        slab = user.plan_slab or "A"
        label, days, price = PLAN_SLABS[slab][plan_key]

    except Exception:
        print("BAD CALLBACK:", callback.data)
        await callback.answer("Invalid plan ❌", show_alert=True)
        return

    payment_link = await create_payment_link(
        user_id=callback.from_user.id,
        channel_id=channel_id,
        days=days,
        price=price
    )

    await callback.message.answer(
        f"💳 <b>{label}</b>\n\nPay here:\n{payment_link}"
    )
