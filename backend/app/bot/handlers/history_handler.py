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
from backend.app.db.models import PaymentHistory, User, Membership, Channel

router = Router()
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x]

class HistoryStates(StatesGroup):
    waiting_for_search_name = State()

def _back_to_history_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📜 Search Another Name", callback_data="admin_history_search")],
        [InlineKeyboardButton(text="🔙 Back to Admin Menu", callback_data="admin_back_main")]
    ])

@router.message(Command("history"))
async def history_command_handler(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS: return
    await state.set_state(HistoryStates.waiting_for_search_name)
    await message.answer("🔍 Enter the name to search legacy & live data:", 
                         reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel", callback_data="admin_cancel_state")]]))

@router.callback_query(F.data == "admin_history_search")
async def history_callback_handler(callback: CallbackQuery, state: FSMContext):
    await state.set_state(HistoryStates.waiting_for_search_name)
    await callback.message.edit_text("🔍 Enter the name to search legacy & live data:",
                                     reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel", callback_data="admin_cancel_state")]]))
    await callback.answer()

@router.message(HistoryStates.waiting_for_search_name)
async def process_combined_search(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS: return
    search_query = message.text.strip()
    
    processing_msg = await message.answer("⏳ Searching...")

    async with async_session() as session:
        # 1. Fetch Legacy
        legacy_res = await session.execute(select(PaymentHistory).where(PaymentHistory.name.ilike(f"%{search_query}%")))
        legacy_records = legacy_res.scalars().all()
        
        # 2. Fetch Live
        live_res = await session.execute(select(User).where(User.full_name.ilike(f"%{search_query}%")))
        live_users = live_res.scalars().all()

        user_profiles = {}
        for l_user in live_users:
            memb_res = await session.execute(select(Membership, Channel).join(Channel).where(Membership.user_id == l_user.id))
            user_profiles[l_user.full_name.strip()] = {"user_obj": l_user, "memberships": memb_res.all()}

        legacy_grouped = collections.defaultdict(list)
        for rec in legacy_records:
            legacy_grouped[rec.name.strip()].append(rec)

        all_names = set(user_profiles.keys()) | set(legacy_grouped.keys())

        if not all_names:
            await processing_msg.edit_text("❌ No records found.", reply_markup=_back_to_history_menu())
            await state.clear()
            return

        await processing_msg.delete()

        # Send individual messages per user
        for profile_name in sorted(all_names):
            # A. Live Section
            text = f"👤 <b>PROFILE: {profile_name}</b>\n"
            if profile_name in user_profiles:
                p = user_profiles[profile_name]
                text += f"🌐 <b>Live Bot Account:</b> Tier {p['user_obj'].current_tier}\n"
                if p['memberships']:
                    for m, c in p['memberships']:
                        icon = "✅" if m.is_active else "❌"
                        exp = m.expiry_date.strftime("%d %b %Y") if m.expiry_date else "N/A"
                        text += f"{icon} <i>{c.name}</i> (Exp: {exp})\n"
                else:
                    text += "📭 <i>No active bot memberships.</i>\n"
            else:
                text += "🌐 <b>Live Bot Account:</b> ❌ No account found.\n"

            # B. Separator
            text += "\n➖➖➖➖➖➖➖➖➖➖➖➖\n\n"

            # C. Legacy Section
            if profile_name in legacy_grouped:
                txs = legacy_grouped[profile_name]
                total = sum(float(tx.amount) for tx in txs)
                highest = max(float(tx.amount) for tx in txs)
                text += f"📜 <b>Legacy Financial History</b>\n💰 <b>Total Spent:</b> ₹{total:,.2f}\n💎 <b>Highest Tx:</b> ₹{highest:,.2f}\n📋 <b>Records ({len(txs)} total):</b>\n"
                for tx in txs[:5]:
                    text += f"📅 <code>{tx.date.strftime('%Y-%m-%d')}</code> | ₹{float(tx.amount):.0f} | <i>{tx.group_name}</i>\n"
            else:
                text += "📜 <b>Legacy Financial History:</b> ❌ No records found."

            await message.answer(text, parse_mode="HTML")

    await state.clear()
    await message.answer("✅ Search complete.", reply_markup=_back_to_history_menu())