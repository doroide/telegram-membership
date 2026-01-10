from aiogram import Router
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command

from sqlalchemy import select, func
from backend.app.db.session import async_session
from backend.app.db.models import User

ADMIN_ID = 5793624035

router = Router()

PAGE_SIZE = 20


def is_admin(message: Message):
    return message.from_user.id == ADMIN_ID


# -------------------------------------------------------
# /admin — show admin menu
# -------------------------------------------------------
@router.message(Command("admin"))
async def admin_menu(message: Message):

    if not is_admin(message):
        return await message.answer("❌ You are not authorized.")

    text = (
        "🛠 <b>Admin Panel</b>\n\n"
        "Commands:\n"
        "• /users — View users list\n"
        "• /broadcast — Send message to all users\n"
        "• /revenue — Total revenue\n"
        "• /revenue_month — This month's revenue\n"
        "• /revenue_summary — Revenue history\n"
    )

    await message.answer(text, parse_mode="HTML")


# -------------------------------------------------------
# FEATURE A: USERS LIST (PAGINATION)
# -------------------------------------------------------
@router.message(Command("users"))
async def users_main_menu(message: Message):

    if not is_admin(message):
        return await message.answer("❌ You are not authorized.")

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🟢 Active Users", callback_data="users_active_0")],
            [InlineKeyboardButton(text="🔴 Expired Users", callback_data="users_expired_0")],
        ]
    )
    
    await message.answer("Select a category:", reply_markup=keyboard)


@router.callback_query(lambda c: c.data.startswith("users_"))
async def users_pagination(callback):

    if callback.from_user.id != ADMIN_ID:
        return await callback.answer("Not allowed", show_alert=True)

    _, mode, page = callback.data.split("_")
    page = int(page)

    async with async_session() as session:

        if mode == "active":
            query = select(User).where(User.status == "active")
        else:
            query = select(User).where(User.status != "active")

        all_users = (await session.execute(query)).scalars().all()

    start = page * PAGE_SIZE
    end = start + PAGE_SIZE
    chunk = all_users[start:end]

    total_pages = (len(all_users) - 1) // PAGE_SIZE + 1 if all_users else 1

    text = f"📄 <b>{mode.capitalize()} Users — Page {page+1}/{total_pages}</b>\n\n"

    if not chunk:
        text += "No users found."
    else:
        for u in chunk:
            text += f"• {u.telegram_id} — {u.plan_id}\n"

    buttons = []

    if page > 0:
        buttons.append(InlineKeyboardButton(
            text="◀ Prev",
            callback_data=f"users_{mode}_{page-1}"
        ))

    if end < len(all_users):
        buttons.append(InlineKeyboardButton(
            text="Next ▶",
            callback_data=f"users_{mode}_{page+1}"
        ))

    keyboard = InlineKeyboardMarkup(inline_keyboard=[buttons] if buttons else [])

    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    await callback.answer()


# -------------------------------------------------------
# FEATURE B: BROADCAST MESSAGE
# -------------------------------------------------------
@router.message(Command("broadcast"))
async def broadcast(message: Message):

    if not is_admin(message):
        return

    args = message.text.split(" ", 1)

    if len(args) < 2:
        return await message.answer(
            "📢 Usage:\n<b>/broadcast Your message here</b>",
            parse_mode="HTML"
        )

    text_to_send = args[1]

    await message.answer("⏳ Sending broadcast...")

    async with async_session() as session:
        users = (await session.execute(select(User.telegram_id))).scalars().all()

    sent = 0
    failed = 0

    from backend.bot.bot import bot

    for uid in users:
        try:
            await bot.send_message(uid, text_to_send)
            sent += 1
        except:
            failed += 1

    await message.answer(
        f"📢 <b>Broadcast Complete</b>\n\n"
        f"✅ Sent: {sent}\n"
        f"❌ Failed: {failed}",
        parse_mode="HTML"
    )
