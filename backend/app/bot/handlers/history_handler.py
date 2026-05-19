import os
import collections
from datetime import datetime, timezone
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from sqlalchemy import select

from backend.app.db.session import async_session
from backend.app.db.models import PaymentHistory, User, Membership, Channel

router = Router()

# Pull Admin IDs securely matching your core configuration pattern
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x]

class HistoryStates(StatesGroup):
    waiting_for_search_name = State()

def _back_to_history_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📜 Search Another Name", callback_data="admin_history_search")],
        [InlineKeyboardButton(text="🔙 Back to Admin Menu", callback_data="admin_back_main")]
    ])

# =====================================================
# ENTRY PATHWAY: Command Trigger
# =====================================================
@router.message(Command("history"))
async def history_command_handler(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    await state.set_state(HistoryStates.waiting_for_search_name)
    await message.answer(
        "📜 <b>User Profile & History Center</b>\n\n"
        "Send me the <b>Name</b> of the member you want to look up. "
        "The bot will match both live bot subscriptions and old Excel records:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Cancel Search", callback_data="admin_cancel_state")]
        ])
    )

# =====================================================
# ENTRY PATHWAY: Callback Menu Button Trigger
# =====================================================
@router.callback_query(F.data == "admin_history_search")
async def history_callback_handler(callback: CallbackQuery, state: FSMContext):
    try:
        await callback.answer()
    except Exception:
        pass

    if callback.from_user.id not in ADMIN_IDS:
        try:
            await callback.message.answer("⛔ Access Denied: Admin Privileges Required.")
        except Exception:
            pass
        return

    await state.set_state(HistoryStates.waiting_for_search_name)
    await callback.message.edit_text(
        "📜 <b>User Profile & History Center</b>\n\n"
        "Send me the <b>Name</b> of the member you want to look up. "
        "The bot will match both live bot subscriptions and old Excel records:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Cancel Search", callback_data="admin_cancel_state")]
        ])
    )

# =====================================================
# PROCESSING PIPELINE: Dual-Engine Merge Query
# =====================================================
@router.message(HistoryStates.waiting_for_search_name)
async def process_combined_search(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return

    search_query = message.text.strip() if message.text else ""
    
    if len(search_query) < 2:
        await message.answer(
            "⚠️ Search name too short! Please type at least <b>2 characters</b> to search.",
            parse_mode="HTML"
        )
        return

    processing_msg = await message.answer("🔍 Querying databases and compiling user profiles...")

    try:
        async with async_session() as session:
            # 1. FETCH LEGACY EXCEL ENTRIES
            legacy_stmt = (
                select(PaymentHistory)
                .where(PaymentHistory.name.ilike(f"%{search_query}%"))
                .order_by(PaymentHistory.date.desc())
            )
            legacy_res = await session.execute(legacy_stmt)
            legacy_records = legacy_res.scalars().all()

            # 2. FETCH LIVE BOT ACCOUNTS WITH ACTIVE MEMBERSHIPS
            live_stmt = (
                select(User)
                .where(User.full_name.ilike(f"%{search_query}%"))
            )
            live_res = await session.execute(live_stmt)
            live_users = live_res.scalars().all()

            # We pre-fetch memberships for matching users to dodge circular lazy-loading locks
            user_profiles = {}
            for l_user in live_users:
                memb_stmt = (
                    select(Membership, Channel)
                    .join(Channel, Membership.channel_id == Channel.id)
                    .where(Membership.user_id == l_user.id)
                    .order_by(Membership.is_active.desc(), Membership.expiry_date.desc())
                )
                memb_res = await session.execute(memb_stmt)
                user_profiles[l_user.full_name.strip()] = {
                    "user_obj": l_user,
                    "memberships": memb_res.all()
                }

    except Exception as db_err:
        print(f"[CRITICAL COMBINED SEARCH DB ERROR]: {db_err}")
        await state.clear()
        await processing_msg.edit_text(
            f"🚨 <b>Database Lookup Error:</b>\n<code>{str(db_err)}</code>",
            parse_mode="HTML",
            reply_markup=_back_to_history_menu()
        )
        return

    # Extract all distinct unique names found across BOTH databases
    all_names = set()
    
    legacy_grouped = collections.defaultdict(list)
    for rec in legacy_records:
        c_name = rec.name.strip()
        legacy_grouped[c_name].append(rec)
        all_names.add(c_name)
        
    for l_name in user_profiles.keys():
        all_names.add(l_name)

    if not all_names:
        await state.clear()
        await processing_msg.edit_text(
            f"❌ No records found matching <b>'{search_query}'</b> in legacy or live data.",
            parse_mode="HTML",
            reply_markup=_back_to_history_menu()
        )
        return

    # Build response payload
    response_text = f"📊 <b>Found {len(all_names)} unique matching profiles:</b>\n\n"
    
    # Strict display limit to protect against Telegram's 4096 character limit
    display_limit = 4
    current_count = 0

    for profile_name in sorted(all_names):
        if current_count >= display_limit:
            response_text += "⚠️ <i>Too many matches found. Please type a more specific name to narrow results.</i>\n"
            break
            
        current_count += 1
        response_text += f"👤 <b>PROFILE: {profile_name}</b>\n"
        
        # PART A: DISPLAY LIVE BOT SUBSCRIPTIONS FIRST (IF ANY EXIST)
        if profile_name in user_profiles:
            profile_data = user_profiles[profile_name]
            u_obj = profile_data["user_obj"]
            membs = profile_data["memberships"]
            
            username_display = f"@{u_obj.username}" if u_obj.username else "N/A"
            response_text += (
                f"├─ 🌐 <b>Live Bot Account</b>\n"
                f"│  🆔 ID: <code>{u_obj.telegram_id}</code> | {username_display}\n"
                f"│  🎯 Current Tier: {u_obj.current_tier}\n"
            )
            
            if membs:
                response_text += "│  📥 <b>Current Memberships:</b>\n"
                for membership, channel in membs:
                    status_icon = "✅" if membership.is_active else "❌"
                    exp_date = membership.expiry_date.strftime("%d %b %Y") if membership.expiry_date else "N/A"
                    response_text += f"│  {status_icon} <i>{channel.name}</i> (Expires: {exp_date})\n"
            else:
                response_text += "│  📭 <i>No active or expired bot memberships.</i>\n"
        else:
            response_text += "├─ 🌐 <b>Live Bot Account:</b> ❌ No account found inside bot database.\n"

        # PART B: DISPLAY LEGACY TRANSACTION DATA DIRECTLY BELOW IT
        if profile_name in legacy_grouped:
            tx_list = legacy_grouped[profile_name]
            
            # Safe calculation casting to float explicitly
            total_legacy = sum(float(tx.amount) for tx in tx_list)
            highest_legacy = max(float(tx.amount) for tx in tx_list)
            
            response_text += (
                f"└─ 📜 <b>Legacy Financial History</b>\n"
                f"   💰 Total Spent: <b>₹{total_legacy:,.2f}</b>\n"
                f"   💎 Highest Single Tx: ₹{highest_legacy:,.2f}\n"
                f"   📋 <b>Old Records ({len(tx_list)} total):</b>\n"
            )
            
            # Show only the last 5 transactions per person if they have huge history lines to prevent bloating
            for tx in tx_list[:5]:
                f_date = tx.date.strftime("%Y-%m-%d") if isinstance(tx.date, datetime) else str(tx.date)[:10]
                response_text += f"   📅 <code>{f_date}</code> | ₹{float(tx.amount):.0f} | <i>{tx.group_name}</i>\n"
                
            if len(tx_list) > 5:
                response_text += f"   ... and {len(tx_list) - 5} older rows.\n"
        else:
            response_text += "└─ 📜 <b>Legacy Financial History:</b> ❌ No old Excel data lines.\n"
            
        response_text += "────────────────────\n"

    # Safely clear active machine state right before pushing data to telegram
    await state.clear()
    
    try:
        await processing_msg.edit_text(
            response_text,
            parse_mode="HTML",
            reply_markup=_back_to_history_menu()
        )
    except Exception as telegram_err:
        print(f"[TELEGRAM RESPONSE PACK PACKING FAIL]: {telegram_err}")
        await message.answer(
            "⚠️ <b>Character Limit Safety Warning</b>\n\n"
            "Profiles compiled successfully, but the resulting layout text block is too massive to output. "
            "Please try again using a more specific first name or last name.",
            parse_mode="HTML",
            reply_markup=_back_to_history_menu()
        )