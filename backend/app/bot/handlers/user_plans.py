from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select

from backend.app.db.session import async_session
from backend.app.db.models import User, Channel
from backend.app.services.payment_service import create_payment_link


router = Router()


# =====================================================
# PLAN DEFINITIONS (Lifetime = 2 YEARS = 730 days)
# =====================================================

PLAN_SLABS = {
    "A": [
        ("1M ₹49", 30, 49),
        ("4M ₹199", 120, 199),
        ("6M ₹299", 180, 299),
        ("12M ₹599", 365, 599),
        ("Lifetime ₹999", 730, 999),
    ],
    "B": [
        ("1M ₹99", 30, 99),
        ("4M ₹299", 120, 299),
        ("6M ₹599", 180, 599),
        ("12M ₹799", 365, 799),
        ("Lifetime ₹999", 730, 999),
    ],
    "C": [
        ("1M ₹199", 30, 199),
        ("3M ₹399", 90, 399),
        ("6M ₹599", 180, 599),
        ("12M ₹799", 365, 799),
        ("Lifetime ₹999", 730, 999),
    ],
    "LIFETIME": [
        ("Lifetime ₹999", 730, 999),
    ],
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
            await callback.answer("Contact admin first to activate plan ❌", show_alert=True)
            return

        slab = user.plan_slab or "A"

        channel = await session.get(Channel, channel_id)

    plans = PLAN_SLABS.get(slab, PLAN_SLABS["A"])

    buttons = []

    for text, days, price in plans:
        buttons.append([
            InlineKeyboardButton(
                text=text,
                # ✅ CLEAN + SAFE FORMAT
                callback_data=f"buy_{channel_id}_{days}_{price}"
            )
        ])

    kb = InlineKeyboardMarkup(inline_keyboard=buttons)

    # ✅ ALWAYS send new message (prevents Telegram cache issues)
    await callback.message.answer(
        f"💳 <b>{channel.name}</b>\n\nChoose your plan:",
        reply_markup=kb
    )

    await callback.answer()


# =====================================================
# USER CLICKED BUY PLAN
# =====================================================

@router.callback_query(F.data.startswith("buy_"))
async def buy_plan(callback: CallbackQuery):

    print("CALLBACK:", callback.data)  # debug log

    try:
        # Expected format → buy_channel_days_price
        _, channel_id, days, price = callback.data.split("_")

        channel_id = int(channel_id)
        days = int(days)
        price = int(price)

    except Exception:
        await callback.answer("Invalid plan selected ❌", show_alert=True)
        return

    payment_link = await create_payment_link(
        user_id=callback.from_user.id,
        channel_id=channel_id,
        days=days,
        price=price
    )

    await callback.message.answer(
        f"💳 <b>Payment Link</b>\n\n{payment_link}\n\n"
        "After payment you will receive invite automatically ✅"
    )

    await callback.answer()
