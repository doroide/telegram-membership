from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from backend.app.db.session import async_session
from backend.app.db.models import Channel

router = Router()

# =====================================================
# FSM
# =====================================================
class AddChannelFSM(StatesGroup):
    waiting_name = State()
    waiting_chat_id = State()
    waiting_visibility = State()

# =====================================================
# /addchannel
# =====================================================
@router.message(Command("addchannel"))
async def add_channel_start(message: Message, state: FSMContext):
    await state.set_state(AddChannelFSM.waiting_name)
    await message.answer("Send channel name")

# =====================================================
# STEP 1 — NAME
# =====================================================
@router.message(AddChannelFSM.waiting_name)
async def get_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(AddChannelFSM.waiting_chat_id)
    await message.answer("Send Telegram chat_id\n(example: -1001234567890)")

# =====================================================
# STEP 2 — CHAT ID
# =====================================================
@router.message(AddChannelFSM.waiting_chat_id)
async def get_chat_id(message: Message, state: FSMContext):
    chat_id = int(message.text)
    await state.update_data(chat_id=chat_id)
    
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Public (Channels 1-4)", callback_data="vis_public"),
                InlineKeyboardButton(text="Private (Channels 5-10)", callback_data="vis_private"),
            ]
        ]
    )
    await state.set_state(AddChannelFSM.waiting_visibility)
    await message.answer("Visibility?", reply_markup=kb)

# =====================================================
# STEP 3 — SAVE
# =====================================================
@router.callback_query(AddChannelFSM.waiting_visibility, F.data.startswith("vis_"))
async def save_channel(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    is_public = callback.data == "vis_public"
    
    async with async_session() as session:
        channel = Channel(
            name=data["name"],
            telegram_chat_id=data["chat_id"],
            is_public=is_public,
            is_active=True
        )
        session.add(channel)
        await session.commit()
    
    visibility_text = "Public (Visible to all)" if is_public else "Private (Hidden until purchased)"
    
    await callback.message.edit_text(
        f"✅ Channel added successfully\n\n"
        f"📱 Name: {data['name']}\n"
        f"🔑 Chat ID: {data['chat_id']}\n"
        f"👁 Visibility: {visibility_text}"
    )
    await state.clear()