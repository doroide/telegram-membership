import os
from datetime import datetime, timedelta

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery, Message,
    InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
)
from sqlalchemy import select

from backend.app.db.session import async_session
from backend.app.db.models import UpiPayment, User, Membership, Payment, Channel
from backend.app.services.payment_service import UPI_ID, UPI_QR_PATH

router = Router()

# Cached after first send to avoid re-uploading
_upi_qr_file_id: str | None = None

VALIDITY_LABELS = {
    30: "1 Month", 90: "3 Months", 120: "4 Months",
    180: "6 Months", 365: "1 Year", 730: "Lifetime"
}

def validity_label(days: int) -> str:
    return VALIDITY_LABELS.get(days, f"{days} Days")


# ── States ───────────────────────────────────────────────────────────

class UpiStates(StatesGroup):
    waiting_for_proof = State()


# ── Entry point called from channel_plans.py ─────────────────────────

async def show_upi_payment(
    callback: CallbackQuery,
    channel_id: int,
    days: int,
    price: int,
    channel_name: str,
    state: FSMContext
):
    global _upi_qr_file_id

    await state.update_data(
        upi_channel_id=channel_id,
        upi_days=days,
        upi_price=price,
        upi_channel_name=channel_name
    )

    caption = (
        f"💳 *Complete Your Payment*\n\n"
        f"📦 *Plan:* {validity_label(days)} Access\n"
        f"💰 *Amount:* \u20b9{price}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🏦 *UPI ID:* `{UPI_ID}`\n"
        f"☝️ _Tap & hold UPI ID to copy_\n"
        f"━━━━━━━━━━━━━━━\n\n"
        f"📌 *How to Pay:*\n"
        f"• Scan the QR code above\n"
        f"• OR pay using the UPI ID\n\n"
        f"🚀 After payment, click below 👇"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="✅ I Have Paid",
            callback_data=f"upi_paid:{channel_id}:{days}:{price}"
        )],
        [InlineKeyboardButton(text="🏠 Back to Home", callback_data="cancel_to_home")]
    ])

    try:
        if _upi_qr_file_id:
            msg = await callback.message.answer_photo(
                photo=_upi_qr_file_id,
                caption=caption,
                parse_mode="Markdown",
                reply_markup=keyboard
            )
        else:
            qr_file = FSInputFile(UPI_QR_PATH)
            msg = await callback.message.answer_photo(
                photo=qr_file,
                caption=caption,
                parse_mode="Markdown",
                reply_markup=keyboard
            )
            _upi_qr_file_id = msg.photo[-1].file_id
    except Exception as e:
        print(f"[UPI] QR send failed: {e}")
        await callback.message.answer(
            caption + "\n\n_(QR unavailable — copy UPI ID above)_",
            parse_mode="Markdown",
            reply_markup=keyboard
        )

    try:
        await callback.answer()
    except Exception:
        pass


# ── User: clicked "I Have Paid" ───────────────────────────────────────

@router.callback_query(F.data.startswith("upi_paid:"))
async def upi_paid_clicked(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    channel_id = int(parts[1])
    days = int(parts[2])
    price = int(parts[3])

    await state.update_data(upi_channel_id=channel_id, upi_days=days, upi_price=price)
    await state.set_state(UpiStates.waiting_for_proof)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 Back to Home", callback_data="cancel_to_home")]
    ])

    await callback.message.answer(
        "📩 *Send Payment Proof*\n\n"
        "Please send your *payment screenshot* 📸\n\n"
        "🔥 For any issue, contact admin: @doroide47",
        parse_mode="Markdown",
        reply_markup=keyboard
    )
    try:
        await callback.answer()
    except Exception:
        pass


# ── User: sends UTR text or screenshot ───────────────────────────────

@router.message(UpiStates.waiting_for_proof)
async def receive_proof(message: Message, state: FSMContext):
    data = await state.get_data()
    channel_id = data.get("upi_channel_id")
    days = data.get("upi_days")
    price = data.get("upi_price")

    if not channel_id:
        await message.answer("Session expired. Please start over.")
        await state.clear()
        return

    # Determine proof type
    if message.photo:
        proof_type = "screenshot"
        screenshot_file_id = message.photo[-1].file_id
        utr_number = None
    elif message.document:
        proof_type = "screenshot"
        screenshot_file_id = message.document.file_id
        utr_number = None
    elif message.text:
        proof_type = "utr"
        utr_number = message.text.strip()
        screenshot_file_id = None
    else:
        await message.answer(
            "Please send your *payment screenshot* 📸\n\n"
            "🔥 For any issue, contact admin: @doroide47",
            parse_mode="Markdown"
        )
        return

    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        user = result.scalar_one_or_none()
        if not user:
            await message.answer("User not found. Please /start first.")
            await state.clear()
            return

        channel = await session.get(Channel, channel_id)

        upi_payment = UpiPayment(
            user_id=user.id,
            channel_id=channel_id,
            amount=price,
            validity_days=days,
            proof_type=proof_type,
            utr_number=utr_number,
            screenshot_file_id=screenshot_file_id,
            status="pending"
        )
        session.add(upi_payment)
        await session.commit()
        await session.refresh(upi_payment)

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🏠 Back to Home", callback_data="cancel_to_home")]
        ])

        await message.answer(
            "\u23f3 *Payment Under Review*\n\n"
            "Thanks\\! Your payment proof has been received \u2705\n\n"
            "\U0001f50d Our team is verifying your payment\n"
            "\u23f1 This usually takes *a few minutes*\n\n"
            "\U0001f4de Need help? Contact admin: @doroide47\n\n"
            "\U0001f3af You will get access immediately after approval\\.\n"
            "\U0001f64f Please wait\\.\\.\\.",
            parse_mode="MarkdownV2",
            reply_markup=keyboard
        )
        await state.clear()

        await _notify_admin(upi_payment, user, channel, message.from_user)


# ── User: cancel and go back home ────────────────────────────────────

@router.callback_query(F.data == "cancel_to_home")
async def cancel_to_home(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    try:
        await callback.answer()
    except Exception:
        pass

    from backend.app.bot.handlers.start import on_back_home
    await on_back_home(callback)


# ── Admin: notify ─────────────────────────────────────────────────────

async def _notify_admin(upi_payment: UpiPayment, user: User, channel: Channel, tg_user):
    from backend.bot.bot import bot

    admin_ids_str = os.getenv("ADMIN_IDS", "")
    admin_ids = [int(x.strip()) for x in admin_ids_str.split(",") if x.strip().isdigit()]

    username = f"@{tg_user.username}" if tg_user.username else tg_user.full_name

    text = (
        f"\U0001f4b0 *New UPI Payment — Pending Approval*\n\n"
        f"User: {username} (`{tg_user.id}`)\n"
        f"Channel: *{channel.name}*\n"
        f"Plan: *{validity_label(upi_payment.validity_days)}*\n"
        f"Amount: *\u20b9{upi_payment.amount}*\n"
        f"Proof: *{upi_payment.proof_type.upper()}*\n"
        f"Payment ID: `#{upi_payment.id}`"
    )

    if upi_payment.proof_type == "utr":
        text += f"\nUTR: `{upi_payment.utr_number}`"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Approve", callback_data=f"upi_approve:{upi_payment.id}"),
        InlineKeyboardButton(text="❌ Reject", callback_data=f"upi_reject:{upi_payment.id}")
    ]])

    for admin_id in admin_ids:
        try:
            if upi_payment.proof_type == "screenshot" and upi_payment.screenshot_file_id:
                await bot.send_photo(
                    chat_id=admin_id,
                    photo=upi_payment.screenshot_file_id,
                    caption=text,
                    parse_mode="Markdown",
                    reply_markup=keyboard
                )
            else:
                await bot.send_message(
                    chat_id=admin_id,
                    text=text,
                    parse_mode="Markdown",
                    reply_markup=keyboard
                )
        except Exception as e:
            print(f"[UPI] Admin notify failed for {admin_id}: {e}")


# ── Admin: Approve ────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("upi_approve:"))
async def approve_payment(callback: CallbackQuery):
    from backend.bot.bot import bot

    payment_id = int(callback.data.split(":")[1])

    async with async_session() as session:
        upi_payment = await session.get(UpiPayment, payment_id)
        if not upi_payment:
            await callback.answer("Payment not found!", show_alert=True)
            return
        if upi_payment.status != "pending":
            await callback.answer(f"Already {upi_payment.status}!", show_alert=True)
            return

        upi_payment.status = "approved"

        user = await session.get(User, upi_payment.user_id)
        channel = await session.get(Channel, upi_payment.channel_id)

        now = datetime.utcnow()
        expiry = now + timedelta(days=36500 if upi_payment.validity_days == 730 else upi_payment.validity_days)

        result = await session.execute(
            select(Membership).where(
                Membership.user_id == upi_payment.user_id,
                Membership.channel_id == upi_payment.channel_id,
                Membership.is_active == True
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.expiry_date = expiry
            existing.validity_days = upi_payment.validity_days
            existing.amount_paid = upi_payment.amount
            existing.start_date = now
            existing.reminded_7d = False
            existing.reminded_1d = False
            existing.reminded_expired = False
        else:
            session.add(Membership(
                user_id=upi_payment.user_id,
                channel_id=upi_payment.channel_id,
                validity_days=upi_payment.validity_days,
                amount_paid=upi_payment.amount,
                start_date=now,
                expiry_date=expiry,
                is_active=True
            ))

        session.add(Payment(
            user_id=upi_payment.user_id,
            channel_id=upi_payment.channel_id,
            amount=upi_payment.amount,
            payment_id=f"UPI_{upi_payment.id}",
            status="captured"
        ))

        if upi_payment.amount > float(user.highest_amount_paid or 0):
            user.highest_amount_paid = upi_payment.amount

        await session.commit()

        invite_link = None
        try:
            invite = await bot.create_chat_invite_link(
                chat_id=channel.telegram_chat_id,
                member_limit=1,
                expire_date=int((datetime.utcnow() + timedelta(hours=24)).timestamp())
            )
            invite_link = invite.invite_link
        except Exception as e:
            print(f"[UPI] Invite link error: {e}")

        user_msg = (
            f"✅ *Payment Approved!*\n\n"
            f"Channel: *{channel.name}*\n"
            f"Plan: *{validity_label(upi_payment.validity_days)}*\n"
            f"Amount: *\u20b9{upi_payment.amount}*\n\n"
        )
        if invite_link:
            user_msg += f"\U0001f517 *Your Invite Link:*\n{invite_link}\n\n_Link expires in 24 hours._"
        else:
            user_msg += "_Your membership is active! Join the channel if you haven't already._"

        try:
            await bot.send_message(
                chat_id=user.telegram_id,
                text=user_msg,
                parse_mode="Markdown"
            )
        except Exception as e:
            print(f"[UPI] User notify failed: {e}")

        admin_label = f"@{callback.from_user.username}" if callback.from_user.username else "Admin"
        await _edit_admin_msg(callback, f"\n\n✅ *APPROVED* by {admin_label}")
        await callback.answer("✅ Approved!")


# ── Admin: Reject ─────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("upi_reject:"))
async def reject_payment(callback: CallbackQuery):
    from backend.bot.bot import bot

    payment_id = int(callback.data.split(":")[1])

    async with async_session() as session:
        upi_payment = await session.get(UpiPayment, payment_id)
        if not upi_payment:
            await callback.answer("Payment not found!", show_alert=True)
            return
        if upi_payment.status != "pending":
            await callback.answer(f"Already {upi_payment.status}!", show_alert=True)
            return

        upi_payment.status = "rejected"
        await session.commit()

        user = await session.get(User, upi_payment.user_id)

        try:
            await bot.send_message(
                chat_id=user.telegram_id,
                text=(
                    "❌ *Payment Rejected*\n\n"
                    "We couldn't verify your payment proof.\n\n"
                    "Please try again with a *clear screenshot*.\n"
                    "🔥 For any issue, contact admin: @doroide47"
                ),
                parse_mode="Markdown"
            )
        except Exception as e:
            print(f"[UPI] User reject notify failed: {e}")

        admin_label = f"@{callback.from_user.username}" if callback.from_user.username else "Admin"
        await _edit_admin_msg(callback, f"\n\n❌ *REJECTED* by {admin_label}")
        await callback.answer("❌ Rejected.")


# ── Helper: edit admin message after action ───────────────────────────

async def _edit_admin_msg(callback: CallbackQuery, suffix: str):
    try:
        if callback.message.caption:
            await callback.message.edit_caption(
                caption=callback.message.caption + suffix,
                parse_mode="Markdown"
            )
        else:
            await callback.message.edit_text(
                callback.message.text + suffix,
                parse_mode="Markdown"
            )
    except Exception as e:
        print(f"[UPI] Admin msg edit failed: {e}")