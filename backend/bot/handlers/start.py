from aiogram import Router
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import CommandStart

from backend.app.db.session import async_session
from backend.app.db.models import User
#samiksh
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

    # If normal user
    await message.answer(
        "👋 Welcome!\nUse /buy to purchase a plan.\nUse /status to check your membership status."
    )


# -------------------------------------------------------
# When admin clicks the "Admin Panel" button
# -------------------------------------------------------
@router.message(lambda m: m.text == "🛠 Admin Panel")
async def open_admin_panel(message: Message):

    if message.from_user.id != ADMIN_ID:
        return await message.answer("❌ You are not authorized.")

    await message.answer("/admin")
