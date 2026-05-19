from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models import PaymentHistory

router = Router()


# ─── FSM State ────────────────────────────────────────────────────────────────
class HistorySearch(StatesGroup):
    waiting_for_name = State()


# ─── Helpers ──────────────────────────────────────────────────────────────────
async def search_history(session: AsyncSession, query: str) -> dict:
    """Partial, case-insensitive search — returns rows grouped by exact name."""
    stmt = (
        select(PaymentHistory)
        .where(PaymentHistory.name.ilike(f"%{query}%"))
        .order_by(PaymentHistory.name, PaymentHistory.date)
    )
    rows = (await session.execute(stmt)).scalars().all()

    grouped: dict[str, list] = {}
    for row in rows:
        grouped.setdefault(row.name, []).append(row)
    return grouped


def build_result_messages(grouped: dict) -> list[str]:
    """
    Formats grouped rows into Telegram-safe chunks (≤ 3800 chars each).
    Uses plain Markdown (no MarkdownV2 escaping headaches).
    """
    chunks: list[str] = []

    for name, txns in grouped.items():
        total   = sum(t.amount for t in txns)
        highest = max(t.amount for t in txns)

        lines = [f"👤 *{name}*", "─" * 28]

        for t in txns:
            date_str = t.date.strftime("%d %b %Y") if t.date else "N/A"
            group    = t.group_name or "—"
            lines.append(f"  📅 {date_str}   ₹{t.amount:,.0f}   {group}")

        lines += [
            "─" * 28,
            f"  💰 Total paid : ₹{total:,.0f}",
            f"  🏆 Highest    : ₹{highest:,.0f}",
            "",
        ]

        block = "\n".join(lines)

        # Start a new chunk only when current one would overflow
        if chunks and len(chunks[-1]) + len(block) <= 3800:
            chunks[-1] += block
        else:
            chunks.append(block)

    return chunks


# ─── Entry point: "📜 History" button in admin panel ─────────────────────────
@router.callback_query(F.data == "admin_history")
async def history_entry(callback: CallbackQuery, state: FSMContext):
    await state.set_state(HistorySearch.waiting_for_name)
    await callback.message.answer(
        "🔍 *Payment History Search*\n\n"
        "Type a member name (full or partial).\n"
        "_Example: `Raj` matches Rajesh, Rajan, Suraj…_\n\n"
        "Send /cancel to go back.",
        parse_mode="Markdown",
    )
    await callback.answer()


# ─── Cancel anytime ───────────────────────────────────────────────────────────
@router.message(HistorySearch.waiting_for_name, F.text == "/cancel")
async def history_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("↩️ Cancelled. Use /admin to reopen the panel.")


# ─── Receive name → search → reply ───────────────────────────────────────────
@router.message(HistorySearch.waiting_for_name)
async def history_search(message: Message, state: FSMContext, session: AsyncSession):
    query = message.text.strip()

    if len(query) < 2:
        await message.answer("⚠️ Enter at least 2 characters.")
        return

    await message.bot.send_chat_action(message.chat.id, "typing")

    grouped = await search_history(session, query)

    if not grouped:
        await message.answer(
            f"❌ No records found for *\"{query}\"*.\n"
            "Try a shorter or different spelling.",
            parse_mode="Markdown",
        )
        return  # stay in state so admin can try again

    total_people = len(grouped)
    total_txns   = sum(len(v) for v in grouped.values())

    await message.answer(
        f"📊 *{total_people} member(s)* · *{total_txns} transaction(s)* "
        f"matching `{query}`",
        parse_mode="Markdown",
    )

    for chunk in build_result_messages(grouped):
        await message.answer(chunk, parse_mode="Markdown")

    await message.answer(
        "🔁 Search another name, or /cancel to exit.",
    )