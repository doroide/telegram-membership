import os
import collections
from datetime import datetime
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from sqlalchemy import select

from backend.app.db.session import async_session
from backend.app.db.models import PaymentHistory

router = Router()

ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x] [cite: 14]

class HistoryStates(StatesGroup):
    waiting_for_search_name = State()

def _back_to_history_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📜 Search Again", callback_data="admin_history_search")],
        [InlineKeyboardButton(text="🔙 Back to Admin Menu", callback_data="admin_back_main")]
    ])

# =====================================================
# FIXED ENTRY POINT VIA CALLBACK
# =====================================================
@router.callback_query(F.data == "admin_history_search")
async def history_callback_handler(callback: CallbackQuery, state: FSMContext):
    # Guardrail 1: Instantly kill the Telegram loading icon using your constraint rules
    try:
        await callback.answer() [cite: 14]
    except Exception as e:
        print(f"[History Logs] Failed to answer callback query: {e}")

    # Guardrail 2: Security check authorization
    if callback.from_user.id not in ADMIN_IDS: 
        try:
            await callback.message.answer("⛔ Access Denied: Admin Authorization Required.")
        except Exception:
            pass
        return

    # Guardrail 3: Safe transactional view execution
    try:
        await state.set_state(HistoryStates.waiting_for_search_name)
        await callback.message.edit_text(
            "📜 <b>Legacy Payment History Search</b>\n\n"
            "Please type the <b>Name</b> (or part of the name) of the user you want to look up:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ Cancel", callback_data="admin_cancel_state")]
            ])
        )
    except Exception as e:
        print(f"[History Logs] Critical failure rendering text view: {e}")
        # Fallback payload in case edit_text fails due to a mismatched message signature
        await callback.message.answer(
            "📜 <b>Legacy Payment History Search</b>\n\n"
            "Please type the <b>Name</b> of the user you want to look up:",
            parse_mode="HTML"
        )