from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select
from datetime import datetime, timezone

from backend.app.db.session import async_session
from backend.app.db.models import Membership, Channel

router = Router()


@router.message(F.text == "/myplans")
async def myplans_command(message: Message):
    await show_myplans(message)


@router.callback_query(F.data == "myplans")
async def myplans_callback(callback):
    await show_myplans(callback.message)
    await callback.answer()


async def show_myplans(message: Message):
    user_id = message.from_user.id
    now = datetime.now(timezone.utc)

    async with async_session() as session:
        result = await session.execute(
            select(Membership, Channel)
            .join(Channel, Channel.id == Membership.channel_id)
            .where(Membership.is_active == True)
            .order_by(Membership.expiry_date.asc())
        )
        rows = result.all()

    if not rows:
        await message.answer("📭 You have no active subscriptions.")
        return

    for membership, channel in rows:
        days_left = (membership.expiry_date - now).days
        expiry_str = membership.expiry_date.strftime("%d %b %Y")

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔁 Renew",
                    callback_data=f"renew_{channel.id}"
                )
            ]
        ])

        await message.answer(
            f"📺 <b>{channel.name}</b>\n"
            f"⏳ Expires on: {expiry_str}\n"
            f"📅 Days left: {max(days_left, 0)}",
            reply_markup=keyboard
        )
