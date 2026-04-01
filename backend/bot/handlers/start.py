from aiogram import Router
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import CommandStart

from backend.app.db.session import async_session
from backend.app.db.models import User

# Admin ID
ADMIN_ID = 5793624035

router = Router()


@router.message(CommandStart())
async def start(message: Message):

    # If admin, show admin button
    if message.from_user.id == ADMIN_ID:

        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="🛠 Admin Panel")]
            ],
            resize_keyboard=True
        )

        await message.answer(
            "👋 Welcome Admin!\nClick the button below to open your panel:",
            reply_markup=keyboard
        )
        return

    # Normal user start page
    first_name = message.from_user.first_name

    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🚀 Membership")],
            [KeyboardButton(text="📋 My Plans")],
            [KeyboardButton(text="📞 Contact Admin")]
        ],
        resize_keyboard=True
    )

    await message.answer(
        f"""👋 Welcome, {first_name}!

🎬 Premium Content Collections

Steps to get membership:

1️⃣ Click Membership
2️⃣ Select Channel
3️⃣ Choose Plan
4️⃣ Complete Payment

👇 Tap Membership to get started""",
        reply_markup=keyboard
    )


# -------------------------------------------------------
# When admin clicks the "Admin Panel" button
# -------------------------------------------------------
@router.message(lambda m: m.text == "🛠 Admin Panel")
async def open_admin_panel(message: Message):

    if message.from_user.id != ADMIN_ID:
        return await message.answer("❌ You are not authorized.")

    await message.answer("/admin")