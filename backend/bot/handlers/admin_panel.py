from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

from sqlalchemy import select, update
from backend.app.db.session import async_session
from backend.app.db.models import User

from datetime import timedelta, datetime

ADMIN_ID = 5793624035  # change if needed

router = Router()


def is_admin(message: Message):
    return message.from_user.id == ADMIN_ID


# ---------------------------------------------------------
# ADMIN MENU WITH BUTTONS
# ---------------------------------------------------------
@router.message(Command("admin"))
async def admin_menu(message: Message):

    if not is_admin(message):
        return await message.answer("❌ You are not authorized.")

    kb = InlineKeyboardBuilder()
    kb.button(text="📊 Stats", callback_data="admin_stats")
    kb.button(text="🟢 Active Users", callback_data="admin_active")
    kb.button(text="🔴 Expired Users", callback_data="admin_expired")
    kb.button(text="🔍 Search User", callback_data="admin_search")
    kb.button(text="⏳ Extend User", callback_data="admin_extend")
    kb.button(text="🚫 Block User", callback_data="admin_block")
    kb.button(text="📢 Broadcast", callback_data="admin_broadcast")
    kb.adjust(2)

    await message.answer("🛠 <b>Admin Panel</b>", reply_markup=kb.as_markup(), parse_mode="HTML")


# ---------------------------------------------------------
# STATS DISPLAY
# ---------------------------------------------------------
@router.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):

    async with async_session() as session:
        total = (await session.execute(select(User))).scalars().all()
        active = [u for u in total if u.status == "active"]
        expired = [u for u in total if u.status == "inactive"]

    response = (
        f"📊 <b>System Stats</b>\n\n"
        f"👤 Total Users: <b>{len(total)}</b>\n"
        f"🟢 Active Users: <b>{len(active)}</b>\n"
        f"🔴 Expired Users: <b>{len(expired)}</b>\n"
    )

    await callback.message.edit_text(response, parse_mode="HTML")


# ---------------------------------------------------------
# SHOW ACTIVE USERS
# ---------------------------------------------------------
@router.callback_query(F.data == "admin_active")
async def admin_active(callback: CallbackQuery):

    async with async_session() as session:
        users = (await session.execute(
            select(User).where(User.status == "active")
        )).scalars().all()

    if not users:
        return await callback.message.edit_text("🟢 No active users found.")

    msg = "🟢 <b>Active Users:</b>\n\n"
    for u in users:
        msg += f"• {u.telegram_id} — expires on {u.expiry_date}\n"

    await callback.message.edit_text(msg, parse_mode="HTML")


# ---------------------------------------------------------
# SHOW EXPIRED USERS
# ---------------------------------------------------------
@router.callback_query(F.data == "admin_expired")
async def admin_expired(callback: CallbackQuery):

    async with async_session() as session:
        users = (await session.execute(
            select(User).where(User.status == "inactive")
        )).scalars().all()

    if not users:
        return await callback.message.edit_text("🔴 No expired users.")

    msg = "🔴 <b>Expired Users:</b>\n\n"
    for u in users:
        msg += f"• {u.telegram_id} — expired on {u.expiry_date}\n"

    await callback.message.edit_text(msg, parse_mode="HTML")


# ---------------------------------------------------------
# SEARCH USER BY TELEGRAM ID
# ---------------------------------------------------------
@router.callback_query(F.data == "admin_search")
async def ask_search_id(callback: CallbackQuery):
    await callback.message.edit_text("🔍 Send the Telegram ID to search.")
    router.search_mode = True


@router.message()
async def search_user(message: Message):
    if not is_admin(message):
        return

    if not getattr(router, "search_mode", False):
        return

    telegram_id = message.text.strip()

    async with async_session() as session:
        user = (await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )).scalar_one_or_none()

    router.search_mode = False

    if not user:
        return await message.answer("❌ User not found.")

    msg = (
        f"👤 <b>User Details</b>\n\n"
        f"ID: {user.telegram_id}\n"
        f"Plan: {user.plan_id}\n"
        f"Status: {user.status}\n"
        f"Expiry: {user.expiry_date}\n"
    )

    await message.answer(msg, parse_mode="HTML")


# ---------------------------------------------------------
# EXTEND USER PLAN
# ---------------------------------------------------------
@router.callback_query(F.data == "admin_extend")
async def ask_extend_id(callback: CallbackQuery):
    await callback.message.edit_text("⏳ Send Telegram ID to extend expiry.")
    router.extend_mode = True


@router.message()
async def extend_user(message: Message):
    if not is_admin(message):
        return

    if not getattr(router, "extend_mode", False):
        return

    telegram_id = message.text.strip()
    router.extend_mode = False

    async with async_session() as session:
        user = (await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )).scalar_one_or_none()

        if not user:
            return await message.answer("❌ User not found.")

        new_expiry = datetime.utcnow() + timedelta(days=30)
        user.expiry_date = new_expiry
        user.status = "active"

        await session.commit()

    await message.answer(f"✅ Extended expiry to {new_expiry}")


# ---------------------------------------------------------
# BLOCK USER
# ---------------------------------------------------------
@router.callback_query(F.data == "admin_block")
async def ask_block_id(callback: CallbackQuery):
    await callback.message.edit_text("🚫 Send Telegram ID to block user.")
    router.block_mode = True


@router.message()
async def block_user(message: Message):
    if not is_admin(message):
        return

    if not getattr(router, "block_mode", False):
        return

    telegram_id = message.text.strip()
    router.block_mode = False

    async with async_session() as session:
        user = (await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )).scalar_one_or_none()

        if not user:
            return await message.answer("❌ User not found.")

        user.status = "inactive"
        await session.commit()

    await message.answer(f"🚫 User {telegram_id} blocked.")


# ---------------------------------------------------------
# BROADCAST MESSAGE
# ---------------------------------------------------------
@router.callback_query(F.data == "admin_broadcast")
async def ask_broadcast(callback: CallbackQuery):
    await callback.message.edit_text("📢 Send the broadcast message text.")
    router.broadcast_mode = True


@router.message()
async def broadcast(message: Message):
    if not is_admin(message):
        return

    if not getattr(router, "broadcast_mode", False):
        return

    text = message.text
    router.broadcast_mode = False

    async with async_session() as session:
        users = (await session.execute(select(User))).scalars().all()

    sent = 0
    for u in users:
        try:
            await message.bot.send_message(u.telegram_id, text)
            sent += 1
        except:
            pass

    await message.answer(f"📢 Broadcast sent to {sent} users.")
