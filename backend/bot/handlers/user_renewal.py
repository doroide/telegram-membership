from aiogram import Router, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)

from sqlalchemy import select

from backend.app.db.session import async_session
from backend.app.db.models import Membership, Channel, User
from backend.app.services.payment_service import create_payment_link

router = Router()


# ======================================================
# Keyboard
# ======================================================

def plans_keyboard(membership_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1 Month", callback_data=f"renew:{membership_id}:1m")],
        [InlineKeyboardButton(text="3 Months", callback_data=f"renew:{membership_id}:3m")],
        [InlineKeyboardButton(text="6 Months", callback_data=f"renew:{membership_id}:6m")],
        [InlineKeyboardButton(text="12 Months", callback_data=f"renew:{membership_id}:12m")],
    ])


# ======================================================
# /renew
# ======================================================

@router.message(F.text == "/renew")
async def renew_menu(message: Message):

    user_id = message.from_user.id

    async with async_session() as session:

        result = await session.execute(
            select(Membership)
            .where(Membership.user_id == user_id)
            .where(Membership.is_active == True)
        )

        memberships = result.scalars().all()

        if not memberships:
            await message.answer("No active plans.")
            return

        for m in memberships:
            channel = await session.get(Channel, m.channel_id)

            await message.answer(
                f"📺 {channel.name}\nChoose renewal plan:",
                reply_markup=plans_keyboard(m.id)
            )


# ======================================================
# plan selected
# ======================================================

@router.callback_query(F.data.startswith("renew:"))
async def renew_selected(callback: CallbackQuery):

    _, membership_id, plan = callback.data.split(":")
    membership_id = int(membership_id)

    user_id = callback.from_user.id

    # -----------------------------------
    # pricing logic (tier based)
    # -----------------------------------

    BASE_PRICES = {
        "1m": 199,
        "3m": 499,
        "6m": 799,
        "12m": 1299
    }

    async with async_session() as session:

        user = await session.get(User, user_id)

        price = BASE_PRICES[plan]

        if user.tier == "Premium":
            price *= 0.9
        elif user.tier == "Standard":
            price *= 0.95

    payment = create_payment_link(int(price), user_id, f"renew_{membership_id}_{plan}")

    url = payment.get("short_url")

    await callback.message.edit_text(
        f"💳 Pay ₹{int(price)} to renew\n\n{url}"
    )
