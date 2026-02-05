from aiogram import Router, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from datetime import datetime, timedelta
from sqlalchemy import select

from backend.app.db.session import async_session
from backend.app.db.models import User, Channel, Membership


router = Router()


# =====================================================
# FSM STATES
# =====================================================
class AddUserFSM(StatesGroup):
    waiting_user_id = State()
    waiting_channel = State()
    waiting_slab = State()
    waiting_validity = State()
    waiting_amount = State()


# =====================================================
# /adduser COMMAND
# =====================================================
@router.message(Command("adduser"))
async def add_user_start(message: Message, state: FSMContext):
    await state.set_state(AddUserFSM.waiting_user_id)
    await message.answer("Send Telegram user ID")


# =====================================================
# STEP 1 — USER ID
# =====================================================
@router.message(AddUserFSM.waiting_user_id)
async def get_user_id(message: Message, state: FSMContext):
    user_id = int(message.text)

    await state.update_data(telegram_id=user_id)

    # fetch channels
    async with async_session() as session:
        result = await session.execute(
            select(Channel).where(Channel.is_active == True)
        )
        channels = result.scalars().all()

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=c.name, callback_data=f"ch_{c.id}")]
            for c in channels
        ]
    )

    await state.set_state(AddUserFSM.waiting_channel)
    await message.answer("Select channel:", reply_markup=kb)


# =====================================================
# STEP 2 — CHANNEL SELECT
# =====================================================
@router.callback_query(AddUserFSM.waiting_channel, F.data.startswith("ch_"))
async def select_channel(callback: CallbackQuery, state: FSMContext):
    channel_id = int(callback.data.split("_")[1])

    await state.update_data(channel_id=channel_id)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Plan A", callback_data="slab_A"),
                InlineKeyboardButton(text="Plan B", callback_data="slab_B"),
            ],
            [
                InlineKeyboardButton(text="Plan C", callback_data="slab_C"),
                InlineKeyboardButton(text="Lifetime", callback_data="slab_LIFETIME"),
            ]
        ]
    )

    await state.set_state(AddUserFSM.waiting_slab)
    await callback.message.edit_text("Select Plan Slab:", reply_markup=kb)


# =====================================================
# STEP 3 — SLAB SELECT
# =====================================================
@router.callback_query(AddUserFSM.waiting_slab, F.data.startswith("slab_"))
async def select_slab(callback: CallbackQuery, state: FSMContext):
    slab = callback.data.split("_")[1]

    await state.update_data(plan_slab=slab)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="1 Month", callback_data="val_30"),
                InlineKeyboardButton(text="4 Months", callback_data="val_120"),
            ],
            [
                InlineKeyboardButton(text="6 Months", callback_data="val_180"),
                InlineKeyboardButton(text="12 Months", callback_data="val_365"),
            ],
            [
                InlineKeyboardButton(text="Lifetime", callback_data="val_36500"),
            ]
        ]
    )

    await state.set_state(AddUserFSM.waiting_validity)
    await callback.message.edit_text("Select Validity:", reply_markup=kb)


# =====================================================
# STEP 4 — VALIDITY
# =====================================================
@router.callback_query(AddUserFSM.waiting_validity, F.data.startswith("val_"))
async def select_validity(callback: CallbackQuery, state: FSMContext):
    validity = int(callback.data.split("_")[1])

    await state.update_data(validity_days=validity)

    await state.set_state(AddUserFSM.waiting_amount)
    await callback.message.edit_text("Enter amount received (₹):")


# =====================================================
# STEP 5 — AMOUNT + CREATE MEMBERSHIP
# =====================================================
@router.message(AddUserFSM.waiting_amount)
async def save_membership(message: Message, state: FSMContext):
    amount = int(message.text)

    data = await state.get_data()

    telegram_id = data["telegram_id"]
    channel_id = data["channel_id"]
    slab = data["plan_slab"]
    validity_days = data["validity_days"]

    expiry_date = datetime.utcnow() + timedelta(days=validity_days)

    async with async_session() as session:

        # create user if not exists
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar()

        if not user:
            user = User(telegram_id=telegram_id, plan_slab=slab)
            session.add(user)
            await session.flush()

        # create membership
        membership = Membership(
            user_id=user.id,
            channel_id=channel_id,
            plan_slab=slab,
            validity_days=validity_days,
            amount_paid=amount,
            expiry_date=expiry_date,
            is_active=True
        )

        session.add(membership)
        await session.commit()

        # get channel
        channel = await session.get(Channel, channel_id)

    # create invite
    link = await message.bot.create_chat_invite_link(
        chat_id=channel.telegram_chat_id,
        member_limit=1
    )

    await message.answer(
        f"✅ User added\n\n"
        f"Channel: {channel.name}\n"
        f"Expiry: {expiry_date.date()}\n\n"
        f"Invite link:\n{link.invite_link}"
    )

    await state.clear()
