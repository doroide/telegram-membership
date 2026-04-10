import os
from datetime import datetime, timedelta
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select

from backend.app.db.session import async_session
from backend.app.db.models import User, Channel, Membership, Payment
from backend.app.services.tier_engine import (
    TIER_PLANS,
    calculate_tier_from_amount,
    update_user_tier,
    get_price_for_validity
)

router = Router()

ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x]


# =========================================================
# HELPER — FORMAT USER DISPLAY
# =========================================================

def format_user(full_name, username, telegram_id):
    if full_name and username:
        return f"{full_name} (@{username}) | <code>{telegram_id}</code>"
    elif full_name:
        return f"{full_name} | <code>{telegram_id}</code>"
    elif username:
        return f"@{username} | <code>{telegram_id}</code>"
    else:
        return f"<code>{telegram_id}</code>"


# =========================================================
# FSM STATES
# =========================================================
class AdminAddUserStates(StatesGroup):
    enter_user_id = State()
    select_channel = State()
    select_validity = State()
    select_tier = State()
    enter_custom_amount = State()
    confirm = State()


# =========================================================
# /ADDUSER COMMAND
# =========================================================

@router.message(Command("adduser"))
async def adduser_command(message: Message, state: FSMContext):
    """Admin command to manually add user after taking payment"""
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔ This command is for admins only.")
        return
    
    await message.answer(
        "👤 <b>Add User Manually</b>\n\n"
        "Enter the user's Telegram ID:",
        parse_mode="HTML"
    )
    
    await state.set_state(AdminAddUserStates.enter_user_id)


# =====================================================
# STEP 1: ENTER USER ID
# =====================================================

@router.message(AdminAddUserStates.enter_user_id)
async def receive_user_id(message: Message, state: FSMContext):
    """Receive and validate user ID"""
    try:
        user_telegram_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Invalid ID. Please enter a valid Telegram user ID (numbers only).")
        return
    
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == user_telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            user = User(
                telegram_id=user_telegram_id,
                current_tier=3,
                highest_amount_paid=0
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            user_status = "✅ New user created (Default: Tier 3)"
        else:
            user_status = f"✅ Existing user found (Current Tier: {user.current_tier})"

        # ── Store name + username in FSM state ──
        await state.update_data(
            user_id=user.id,
            user_telegram_id=user_telegram_id,
            user_full_name=user.full_name or "",
            user_username=user.username or "",
            existing_user=user is not None
        )
    
    async with async_session() as session:
        result = await session.execute(
            select(Channel).where(Channel.is_active == True).order_by(Channel.id)
        )
        channels = result.scalars().all()
        
        if not channels:
            await message.answer("❌ No channels found. Please add channels first with /addchannel")
            await state.clear()
            return
        
        keyboard = []
        for channel in channels:
            visibility = "🔓 Public" if channel.is_public else "🔒 Private"
            keyboard.append([
                InlineKeyboardButton(
                    text=f"{channel.name} ({visibility})",
                    callback_data=f"adminadd_ch_{channel.id}"
                )
            ])
        
        keyboard.append([
            InlineKeyboardButton(text="❌ Cancel", callback_data="adminadd_cancel")
        ])

        data = await state.get_data()
        user_display = format_user(data["user_full_name"], data["user_username"], user_telegram_id)

        await message.answer(
            f"👤 <b>Add User</b>\n\n"
            f"User: {user_display}\n"
            f"{user_status}\n\n"
            f"Select the channel user has paid for:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
            parse_mode="HTML"
        )
        
        await state.set_state(AdminAddUserStates.select_channel)


# =====================================================
# STEP 2: SELECT CHANNEL
# =====================================================

@router.callback_query(F.data.startswith("adminadd_ch_"), AdminAddUserStates.select_channel)
async def channel_selected(callback: CallbackQuery, state: FSMContext):
    """Handle channel selection"""
    channel_id = int(callback.data.split("_")[2])
    
    async with async_session() as session:
        result = await session.execute(
            select(Channel).where(Channel.id == channel_id)
        )
        channel = result.scalar_one_or_none()
        
        if not channel:
            await callback.answer("Channel not found", show_alert=True)
            return
        
        await state.update_data(channel_id=channel_id, channel_name=channel.name)
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="1 Month", callback_data="adminadd_val_30")],
            [InlineKeyboardButton(text="3 Months", callback_data="adminadd_val_90")],
            [InlineKeyboardButton(text="4 Months", callback_data="adminadd_val_120")],
            [InlineKeyboardButton(text="6 Months", callback_data="adminadd_val_180")],
            [InlineKeyboardButton(text="1 Year", callback_data="adminadd_val_365")],
            [InlineKeyboardButton(text="Lifetime", callback_data="adminadd_val_730")],
            [InlineKeyboardButton(text="🔙 Back", callback_data="adminadd_back_channel")]
        ])
        
        await callback.message.edit_text(
            f"📺 <b>Channel:</b> {channel.name}\n\n"
            f"Select validity period:",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
        await state.set_state(AdminAddUserStates.select_validity)
    
    await callback.answer()


# =====================================================
# STEP 3: SELECT VALIDITY
# =====================================================

@router.callback_query(F.data.startswith("adminadd_val_"), AdminAddUserStates.select_validity)
async def validity_selected(callback: CallbackQuery, state: FSMContext):
    """Handle validity selection and show tier options"""
    validity_days = int(callback.data.split("_")[2])
    
    validity_display = {
        30: "1 Month",
        90: "3 Months",
        120: "4 Months",
        180: "6 Months",
        365: "1 Year",
        730: "Lifetime"
    }
    
    is_lifetime = validity_days == 730
    
    await state.update_data(
        validity_days=validity_days,
        validity_display=validity_display[validity_days],
        is_lifetime=is_lifetime
    )
    
    data = await state.get_data()
    channel_id = data["channel_id"]
    channel_name = data["channel_name"]
    
    tier_options = []
    
    if channel_id == 1:
        tiers_to_show = [1, 2, 3, 4]
    else:
        tiers_to_show = [3, 4]
    
    for tier in tiers_to_show:
        price = get_price_for_validity(tier, validity_days)
        if price:
            tier_name = TIER_PLANS[tier]["name"]
            tier_options.append([
                InlineKeyboardButton(
                    text=f"{tier_name}: ₹{price}",
                    callback_data=f"adminadd_tier_{tier}_{price}"
                )
            ])
    
    tier_options.append([
        InlineKeyboardButton(
            text="💰 Custom Amount",
            callback_data="adminadd_custom_amount"
        )
    ])
    
    tier_options.append([
        InlineKeyboardButton(text="🔙 Back", callback_data="adminadd_back_validity")
    ])
    
    await callback.message.edit_text(
        f"📺 <b>Channel:</b> {channel_name}\n"
        f"⏰ <b>Validity:</b> {validity_display[validity_days]}\n\n"
        f"Select tier and amount user paid:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=tier_options),
        parse_mode="HTML"
    )
    
    await state.set_state(AdminAddUserStates.select_tier)
    await callback.answer()


# =====================================================
# STEP 4A: SELECT TIER (STANDARD AMOUNT)
# =====================================================

@router.callback_query(F.data.startswith("adminadd_tier_"), AdminAddUserStates.select_tier)
async def tier_selected(callback: CallbackQuery, state: FSMContext):
    """Handle tier selection with standard pricing"""
    parts = callback.data.split("_")
    tier = int(parts[2])
    amount = int(parts[3])
    
    await state.update_data(tier=tier, amount=amount)
    
    data = await state.get_data()
    user_display = format_user(data["user_full_name"], data["user_username"], data["user_telegram_id"])

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Confirm & Activate", callback_data="adminadd_confirm")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="adminadd_back_tier")]
    ])
    
    await callback.message.edit_text(
        f"📋 <b>Confirmation</b>\n\n"
        f"👤 User: {user_display}\n"
        f"📺 Channel: {data['channel_name']}\n"
        f"⏰ Validity: {data['validity_display']}\n"
        f"🎯 Tier: {tier}\n"
        f"💰 Amount: ₹{amount}\n\n"
        f"⚠️ <b>Note:</b> User has already paid. Membership will activate immediately.",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    
    await state.set_state(AdminAddUserStates.confirm)
    await callback.answer()


# =====================================================
# STEP 4B: CUSTOM AMOUNT
# =====================================================

@router.callback_query(F.data == "adminadd_custom_amount", AdminAddUserStates.select_tier)
async def custom_amount_prompt(callback: CallbackQuery, state: FSMContext):
    """Prompt for custom amount entry"""
    await callback.message.edit_text(
        "💰 <b>Custom Amount</b>\n\n"
        "Enter the amount user paid (in rupees):\n\n"
        "Example: <code>350</code>",
        parse_mode="HTML"
    )
    
    await state.set_state(AdminAddUserStates.enter_custom_amount)
    await callback.answer()


@router.message(AdminAddUserStates.enter_custom_amount)
async def receive_custom_amount(message: Message, state: FSMContext):
    """Receive custom amount and ask for tier selection"""
    try:
        amount = int(message.text.strip())
        
        if amount <= 0:
            await message.answer("❌ Amount must be greater than 0. Please try again.")
            return
        
        await state.update_data(amount=amount)
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Tier 1 (Budget)", callback_data="adminadd_customtier_1")],
            [InlineKeyboardButton(text="Tier 2 (Standard)", callback_data="adminadd_customtier_2")],
            [InlineKeyboardButton(text="Tier 3 (Premium)", callback_data="adminadd_customtier_3")],
            [InlineKeyboardButton(text="Tier 4 (Elite)", callback_data="adminadd_customtier_4")],
            [InlineKeyboardButton(text="🔙 Cancel", callback_data="adminadd_back_tier")]
        ])
        
        await message.answer(
            f"💰 <b>Custom Amount: ₹{amount}</b>\n\n"
            f"Select which tier to assign to this user:",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
    except ValueError:
        await message.answer("❌ Invalid amount. Please enter a valid number.")


@router.callback_query(F.data.startswith("adminadd_customtier_"), AdminAddUserStates.enter_custom_amount)
async def custom_tier_selected(callback: CallbackQuery, state: FSMContext):
    """Handle tier selection for custom amount"""
    tier = int(callback.data.split("_")[2])
    
    await state.update_data(tier=tier)
    
    data = await state.get_data()
    user_display = format_user(data["user_full_name"], data["user_username"], data["user_telegram_id"])

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Confirm & Activate", callback_data="adminadd_confirm")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="adminadd_back_tier")]
    ])
    
    await callback.message.edit_text(
        f"📋 <b>Confirmation</b>\n\n"
        f"👤 User: {user_display}\n"
        f"📺 Channel: {data['channel_name']}\n"
        f"⏰ Validity: {data['validity_display']}\n"
        f"🎯 Tier: {tier}\n"
        f"💰 Amount: ₹{data['amount']} (Custom)\n\n"
        f"⚠️ <b>Note:</b> User has already paid. Membership will activate immediately.",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    
    await state.set_state(AdminAddUserStates.confirm)
    await callback.answer()


# =====================================================
# STEP 5: CONFIRM & ACTIVATE
# =====================================================

@router.callback_query(F.data == "adminadd_confirm", AdminAddUserStates.confirm)
async def confirm_and_activate(callback: CallbackQuery, state: FSMContext):
    """Activate membership immediately and send invite to user"""
    data = await state.get_data()
    
    try:
        async with async_session() as session:
            user_result = await session.execute(
                select(User).where(User.id == data["user_id"])
            )
            user = user_result.scalar_one_or_none()
            
            if not user:
                await callback.message.edit_text("❌ User not found.")
                await state.clear()
                return
            
            channel_result = await session.execute(
                select(Channel).where(Channel.id == data["channel_id"])
            )
            channel = channel_result.scalar_one_or_none()
            
            if not channel:
                await callback.message.edit_text("❌ Channel not found.")
                await state.clear()
                return

            # ── Capture tier before update ───────────────────────────
            tier_before = user.current_tier

            # Update user tier
            update_user_tier(
                user,
                data["amount"],
                data["channel_id"],
                data["is_lifetime"]
            )

            tier_after = user.current_tier
            tier_display = (
                f"{tier_before} → {tier_after}" if tier_after != tier_before
                else f"{tier_before}"
            )

            # ── Update highest_amount_paid if new amount is higher ───
            if data["amount"] > float(user.highest_amount_paid or 0):
                user.highest_amount_paid = data["amount"]

            from datetime import datetime, timezone, timedelta
            now = datetime.now(timezone.utc)
            start_date = now
            expiry_date = start_date + timedelta(days=data["validity_days"])
            
            membership = Membership(
                user_id=user.id,
                channel_id=data["channel_id"],
                tier=data["tier"],
                validity_days=data["validity_days"],
                amount_paid=data["amount"],
                start_date=start_date,
                expiry_date=expiry_date,
                is_active=True
            )
            session.add(membership)

            # ── Add Payment record for revenue tracking ──────────────
            session.add(Payment(
                user_id=user.id,
                channel_id=data["channel_id"],
                amount=data["amount"],
                payment_id=f"MANUAL_{user.id}_{data['channel_id']}_{int(now.timestamp())}",
                status="captured"
            ))

            await session.commit()

            user_display = format_user(data["user_full_name"], data["user_username"], data["user_telegram_id"])

            await callback.message.edit_text(
                f"✅ <b>User Added Successfully</b>\n\n"
                f"👤 User: {user_display}\n"
                f"📺 Channel: {data['channel_name']}\n"
                f"⏰ Validity: {data['validity_display']}\n"
                f"🎯 Tier: {tier_display}\n"
                f"💰 Amount: ₹{data['amount']}\n"
                f"📅 Expires: {expiry_date.strftime('%Y-%m-%d')}\n\n"
                f"📤 Sending invite link to user...",
                parse_mode="HTML"
            )
        
        # =========================================
        # SEND INVITE LINK TO USER AUTOMATICALLY
        # =========================================
        try:
            from backend.bot.bot import bot
            
            invite_expiry = int((now + timedelta(hours=24)).timestamp())
            
            invite = await bot.create_chat_invite_link(
                chat_id=channel.telegram_chat_id,
                member_limit=1,
                expire_date=invite_expiry
            )
            
            tier_message = ""
            if user.is_lifetime_member:
                tier_message = "\n💎 You are now a <b>Lifetime Member</b>!"
            elif user.current_tier == 4:
                tier_message = "\n💎 You've unlocked <b>Tier 4 (Elite)</b> pricing!"
            
            await bot.send_message(
                chat_id=data['user_telegram_id'],
                text=(
                    f"🎉 <b>Access Granted!</b>\n\n"
                    f"An admin has given you access to:\n"
                    f"📺 <b>{channel.name}</b>\n\n"
                    f"⏰ Valid till: <b>{expiry_date.strftime('%d %b %Y')}</b>\n"
                    f"🎯 Tier: {data['tier']}"
                    f"{tier_message}\n\n"
                    f"👉 Click below to join (link expires in 24 hrs):\n{invite.invite_link}"
                ),
                parse_mode="HTML"
            )
            
            await callback.message.edit_text(
                f"✅ <b>User Added Successfully</b>\n\n"
                f"👤 User: {user_display}\n"
                f"📺 Channel: {data['channel_name']}\n"
                f"⏰ Validity: {data['validity_display']}\n"
                f"🎯 Tier: {tier_display}\n"
                f"💰 Amount: ₹{data['amount']}\n"
                f"📅 Expires: {expiry_date.strftime('%Y-%m-%d')}\n\n"
                f"✅ Invite link sent to user successfully!",
                parse_mode="HTML"
            )
            
            print(f"✅ Admin added user {data['user_telegram_id']} - Invite sent")
            
        except Exception as e:
            print(f"❌ Error sending invite to user: {e}")
            await callback.message.edit_text(
                f"✅ <b>User Added Successfully</b>\n\n"
                f"👤 User: {user_display}\n"
                f"📺 Channel: {data['channel_name']}\n"
                f"⏰ Validity: {data['validity_display']}\n"
                f"🎯 Tier: {tier_display}\n"
                f"💰 Amount: ₹{data['amount']}\n"
                f"📅 Expires: {expiry_date.strftime('%Y-%m-%d')}\n\n"
                f"⚠️ Membership created but failed to send invite.\n"
                f"User needs to type /start to get access link.",
                parse_mode="HTML"
            )
        
        await state.clear()
        
    except Exception as e:
        await callback.message.edit_text(f"❌ Error activating membership: {str(e)}")
        await state.clear()
    
    await callback.answer()


# =====================================================
# NAVIGATION CALLBACKS
# =====================================================

@router.callback_query(F.data == "adminadd_cancel")
async def admin_add_cancel(callback: CallbackQuery, state: FSMContext):
    """Cancel add user flow"""
    await callback.message.edit_text("❌ User addition cancelled.")
    await state.clear()
    await callback.answer()


@router.callback_query(F.data == "adminadd_back_channel")
async def back_to_channel_selection(callback: CallbackQuery, state: FSMContext):
    """Go back to channel selection"""
    data = await state.get_data()
    
    async with async_session() as session:
        result = await session.execute(
            select(Channel).where(Channel.is_active == True).order_by(Channel.id)
        )
        channels = result.scalars().all()
        
        keyboard = []
        for channel in channels:
            visibility = "🔓 Public" if channel.is_public else "🔒 Private"
            keyboard.append([
                InlineKeyboardButton(
                    text=f"{channel.name} ({visibility})",
                    callback_data=f"adminadd_ch_{channel.id}"
                )
            ])
        
        keyboard.append([
            InlineKeyboardButton(text="❌ Cancel", callback_data="adminadd_cancel")
        ])
        
        await callback.message.edit_text(
            f"👤 <b>Add User</b>\n\n"
            f"User ID: <code>{data['user_telegram_id']}</code>\n\n"
            f"Select the channel user has paid for:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
            parse_mode="HTML"
        )
        
        await state.set_state(AdminAddUserStates.select_channel)
    
    await callback.answer()