from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select

from backend.app.db.session import async_session
from backend.app.db.models import Channel, AccessRequest, User

router = Router()


# ======================================================
# Helpers
# ======================================================

def channel_keyboard(channels, show_all=False):
    buttons = []

    for ch in channels:
        buttons.append([
            InlineKeyboardButton(
                text=f"📺 {ch.name}",
                callback_data=f"channel_view:{ch.id}"
            )
        ])

    if not show_all:
        buttons.append([
            InlineKeyboardButton(text="View All", callback_data="channels_all")
        ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ======================================================
# /channels → show top 3
# ======================================================

@router.message(F.text == "/channels")
async def show_channels(message: Message):
    async with async_session() as session:
        result = await session.execute(
            select(Channel).where(Channel.is_active == True).limit(3)
        )
        channels = result.scalars().all()

    if not channels:
        await message.answer("No channels available right now.")
        return

    await message.answer(
        "📺 *Available Channels*\n\nSelect one to request access:",
        reply_markup=channel_keyboard(channels),
        parse_mode="Markdown"
    )


# ======================================================
# View all channels
# ======================================================

@router.callback_query(F.data == "channels_all")
async def show_all_channels(callback: CallbackQuery):
    async with async_session() as session:
        result = await session.execute(
            select(Channel).where(Channel.is_active == True)
        )
        channels = result.scalars().all()

    await callback.message.edit_text(
        "📺 *All Channels*\n\nSelect one:",
        reply_markup=channel_keyboard(channels, show_all=True),
        parse_mode="Markdown"
    )


# ======================================================
# View single channel
# ======================================================

@router.callback_query(F.data.startswith("channel_view:"))
async def view_channel(callback: CallbackQuery):
    channel_id = int(callback.data.split(":")[1])

    async with async_session() as session:
        result = await session.execute(
            select(Channel).where(Channel.id == channel_id)
        )
        channel = result.scalar_one()

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✅ Apply for Access",
                callback_data=f"channel_apply:{channel.id}"
            )
        ]
    ])

    await callback.message.edit_text(
        f"📺 *{channel.name}*\n\n{channel.description or ''}",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )


# ======================================================
# Apply for access
# ======================================================

@router.callback_query(F.data.startswith("channel_apply:"))
async def apply_channel(callback: CallbackQuery):
    channel_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id

    async with async_session() as session:

        # ensure user exists
        user = await session.get(User, user_id)
        if not user:
            user = User(
                id=user_id,
                username=callback.from_user.username,
                full_name=callback.from_user.full_name
            )
            session.add(user)
            await session.flush()

        request = AccessRequest(
            user_id=user_id,
            channel_id=channel_id
        )

        session.add(request)
        await session.commit()

    await callback.message.edit_text(
        "✅ Request sent!\n\nAdmin will contact you shortly."
    )
