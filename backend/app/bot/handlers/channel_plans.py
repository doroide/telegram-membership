from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select

from backend.app.db.session import async_session
from backend.app.db.models import Channel
from backend.app.config.plans import PLANS
from backend.app.services.payment_service import create_payment_link

router = Router()


# =====================================================
# CHANNEL CLICK → SHOW PLANS
# callback_data = channel_{id}
# =====================================================
@router.callback_query(F.data.startswith("channel_"))
async def show_channel_plans(callback: CallbackQuery):

    channel_id = int(callback.data.split("_")[1])

    async with async_session() as session:
        result = await session.execute(
            select(Channel).where(Channel.id == channel_id)
        )
        channel = result.scalar_one_or_none()

    if not channel:
        await callback.answer("Channel not found", show_alert=True)
        return

    keyboard = []

    # build buttons from PLANS dict
    for plan_id, plan in PLANS.items():

        keyboard.append([
            InlineKeyboardButton(
                text=plan["label"],
                callback_data=f"buy_{channel.id}_{plan_id}"
            )
        ])

    markup = InlineKeyboardMarkup(inline_keyboard=keyboard)

    await callback.message.edit_text(
        f"📺 <b>{channel.name}</b>\n\nChoose your plan 👇",
        reply_markup=markup
    )

    await callback.answer()


# =====================================================
# BUY PLAN → CREATE PAYMENT LINK
# callback_data = buy_{channel_id}_{plan_id}
# =====================================================
@router.callback_query(F.data.startswith("buy_"))
async def buy_plan(callback: CallbackQuery):

    _, channel_id, plan_id = callback.data.split("_")

    plan = PLANS.get(plan_id)

    payment = create_payment_link(
        amount=plan["price"],
        telegram_id=callback.from_user.id,
        channel_id=channel_id,
        plan_id=plan_id
    )

    await callback.message.answer(
        f"💳 <b>{plan['label']}</b>\n"
        f"💰 ₹{plan['price']}\n\n"
        f"👉 Pay here:\n{payment['short_url']}\n\n"
        f"Access will be granted automatically after payment."
    )

    await callback.answer()
