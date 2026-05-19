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

# Pull Admin IDs safely matching your admin_panel configuration pattern
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x]

class HistoryStates(StatesGroup):
    waiting_for_search_name = State()

def _back_to_history_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📜 Search Again", callback_data="admin_history_search")],
        [InlineKeyboardButton(text="🔙 Back to Admin Menu", callback_data="admin_back_main")]
    ])

# =====================================================
# TRIGGER: Entry point via /history command
# =====================================================
@router.message(Command("history"))
async def history_command_handler(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    await state.set_state(HistoryStates.waiting_for_search_name)
    await message.answer(
        "📜 <b>Legacy Payment History Search</b>\n\n"
        "Please type the <b>Name</b> (or part of the name) of the user you want to look up:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Cancel", callback_data="admin_cancel_state")]
        ])
    )

# =====================================================
# TRIGGER: Entry point via Inline Callback Button
# =====================================================
@router.callback_query(F.data == "admin_history_search")
async def history_callback_handler(callback: CallbackQuery, state: FSMContext):
    try:
        await callback.answer()
    except Exception as e:
        print(f"[History Logs] Failed to answer callback query: {e}")

    if callback.from_user.id not in ADMIN_IDS:
        try:
            await callback.message.answer("⛔ Access Denied: Admin Authorization Required.")
        except Exception:
            pass
        return

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
        print(f"[History Logs] Failure rendering text view: {e}")
        await callback.message.answer(
            "📜 <b>Legacy Payment History Search</b>\n\n"
            "Please type the <b>Name</b> of the user you want to look up:",
            parse_mode="HTML"
        )

# =====================================================
# STATE PROCESSING: Handle Text Search Input
# =====================================================
@router.message(HistoryStates.waiting_for_search_name)
async def process_history_search(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return

    search_query = message.text.strip() if message.text else ""
    
    if len(search_query) < 2:
        await message.answer(
            "⚠️ Search query too short! Please type at least <b>2 characters</b>.",
            parse_mode="HTML"
        )
        return

    # Keep FSM state alive during query execution to prevent route hijacking
    processing_msg = await message.answer("🔍 Searching legacy transaction records...")

    try:
        async with async_session() as session:
            stmt = (
                select(PaymentHistory)
                .where(PaymentHistory.name.ilike(f"%{search_query}%"))
                .order_by(PaymentHistory.date.desc())
            )
            result = await session.execute(stmt)
            records = result.scalars().all()

    except Exception as db_err:
        print(f"[CRITICAL DATABASE ERROR]: {db_err}")
        await state.clear()
        await processing_msg.edit_text(
            f"🚨 <b>Database Error:</b>\n<code>{str(db_err)}</code>",
            parse_mode="HTML",
            reply_markup=_back_to_history_menu()
        )
        return

    if not records:
        await state.clear()
        await processing_msg.edit_text(
            f"❌ No legacy records found matching: <b>{search_query}</b>",
            parse_mode="HTML",
            reply_markup=_back_to_history_menu()
        )
        return

    # Group flat rows into clean dictionary collections
    grouped_data = collections.defaultdict(list)
    for record in records:
        cleaned_name = record.name.strip() if record.name else "Unknown"
        grouped_data[cleaned_name].append(record)

    response_text = f"📊 <b>Found {len(records)} transactions across {len(grouped_data)} matches:</b>\n\n"
    display_limit = 5
    current_count = 0

    for individual_name, tx_list in grouped_data.items():
        if current_count >= display_limit:
            response_text += "⚠️ <i>Too many individual matches. Please refine your search query.</i>\n"
            break
            
        current_count += 1
        
        # Safe mathematical evaluations casting decimal objects to float values
        total_spent = sum(float(tx.amount) for tx in tx_list)
        highest_payment = max(float(tx.amount) for tx in tx_list)

        # Build escaping layout metrics using HTML parse modes
        response_text += f"👤 <b>Name: {individual_name}</b>\n"
        response_text += f"💰 <b>Total Invested:</b> ₹{total_spent:,.2f}\n"
        response_text += f"💎 <b>Highest Single Tx:</b> ₹{highest_payment:,.2f}\n"
        response_text += "📋 <b>Transactions:</b>\n"

        for tx in tx_list:
            if isinstance(tx.date, datetime):
                formatted_date = tx.date.strftime("%Y-%m-%d")
            else:
                formatted_date = str(tx.date)[:10]
            
            response_text += f"   📅 <code>{formatted_date}</code> | ₹{float(tx.amount):.0f} | <i>{tx.group_name or 'N/A'}</i>\n"
        
        response_text += "────────────────────\n"

    # Safely discard FSM state right before transmission payload execution
    await state.clear()
    
    try:
        await processing_msg.edit_text(
            response_text,
            parse_mode="HTML",
            reply_markup=_back_to_history_menu()
        )
    except Exception as telegram_err:
        print(f"[TELEGRAM SEND ERROR]: {telegram_err}")
        await message.answer(
            "⚠️ <b>Payload Delivery Error</b>\nResults found but the message structure is too large or contains unescaped markup characters. Try a more specific name lookup.",
            parse_mode="HTML",
            reply_markup=_back_to_history_menu()
        )