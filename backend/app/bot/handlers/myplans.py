from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select
from datetime import datetime, timezone

from backend.app.db.session import async_session
from backend.app.db.models import Membership, Channel, User

router = Router()


# =========================
# /myplans COMMAND
# =========================

@router.message(Command("myplans"))
async def myplans_command(message: Message):
    await show_myplans(message)


# =========================
# MY PLANS BUTTON CALLBACK
# (matches start.py callback_data="my_plans")
# =========================

@router.callback_query(F.data == "my_plans")
async def myplans_callback(callback: CallbackQuery):
    await show_myplans(callback.message)
    await callback.answer()


# =========================
# SHOW USER PLANS
# =========================

async def show_myplans(message: Message):
    telegram_id = message.from_user.id
    now = datetime.now(timezone.utc)

    async with async_session() as session:
        result = await session.execute(
            select(Membership, Channel)
            .join(Channel, Channel.id == Membership.channel_id)
            .join(User, User.id == Membership.user_id)
            .where(
                Membership.is_active == True,
                User.telegram_id == telegram_id
            )
            .order_by(Membership.expiry_date.asc())
        )
        rows = result.all()

    if not rows:
        await message.answer("📭 You have no active subscriptions.")
        return

    for membership, channel in rows:
        days_left = max((membership.expiry_date - now).days, 0)
        expiry_str = membership.expiry_date.strftime("%d %b %Y")

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🔁 Renew",
                        callback_data=f"renew_{channel.id}"
                    )
                ]
            ]
        )

        await message.answer(
            f"📺 <b>{channel.name}</b>\n"
            f"⏳ Expires on: {expiry_str}\n"
            f"📅 Days left: {days_left}",
            reply_markup=keyboard
        )


# =========================
# RENEW BUTTON HANDLER
# =========================

@router.callback_query(F.data.startswith("renew_"))
async def renew_from_myplans(callback: CallbackQuery):
    channel_id = int(callback.data.split("_")[1])

    await callback.message.answer(
        "🔁 <b>Select a plan to renew:</b>",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="View Plans",
                        callback_data=f"userch_{channel_id}"
                    )
                ]
            ]
        )
    )

    await callback.answer()
