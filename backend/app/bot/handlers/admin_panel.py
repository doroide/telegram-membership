import os
from datetime import datetime, timezone
from aiogram import Router, F	
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from sqlalchemy import select, func

from backend.app.db.session import async_session
from backend.app.db.models import User, Channel, Membership, Payment

router = Router()

ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x]


# =====================================================
# ADMIN PANEL MAIN MENU
# =====================================================

@router.message(Command("admin"))
async def admin_panel(message: Message):
    """Show admin panel with all features"""
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔ This command is for admins only.")
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 View All Users", callback_data="admin_view_users")],
        [InlineKeyboardButton(text="➕ Add User Manually", callback_data="admin_add_user")],
        [InlineKeyboardButton(text="📺 View All Channels", callback_data="admin_view_channels")],
        [InlineKeyboardButton(text="🎁 Upsell Stats", callback_data="upsell_stats")],
        [InlineKeyboardButton(text="🎁 Give Offers", callback_data="admin_give_offers")],
        [InlineKeyboardButton(text="➕ Add New Channel", callback_data="admin_add_channel")],
        [InlineKeyboardButton(text="💰 View Payments", callback_data="admin_view_payments")],
        [InlineKeyboardButton(text="📊 Statistics", callback_data="admin_statistics")],
        [InlineKeyboardButton(text="🔍 Search User", callback_data="admin_search_user")],
        [InlineKeyboardButton(text="🦵 Kick User", callback_data="admin_kick_user")],
        [InlineKeyboardButton(text="📢 Broadcast Message", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="🔗 Send Access Links", callback_data="admin_send_links")],
        [InlineKeyboardButton(text="👤 User Info", callback_data="admin_user_info")],
        [InlineKeyboardButton(text="📥 Import Users CSV", callback_data="admin_import_csv")]

    ])
    
    await message.answer(
        "🛠 <b>Admin Panel</b>\n\n"
        "Select an action:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


# =====================================================
# VIEW ALL USERS
# =====================================================

@router.callback_query(F.data == "admin_view_users")
async def view_all_users(callback: CallbackQuery):
    """Display all users with pagination"""
    async with async_session() as session:
        result = await session.execute(
            select(User).order_by(User.created_at.desc()).limit(10)
        )
        users = result.scalars().all()
        
        if not users:
            await callback.message.edit_text(
                "❌ No users found.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 Back", callback_data="admin_back_main")]
                ])
            )
            await callback.answer()
            return
        
        text = "👥 <b>Users (Last 10):</b>\n\n"
        
        for user in users:
            tier_display = f"Tier {user.current_tier}"
            if user.is_lifetime_member:
                tier_display = f"Lifetime (₹{user.lifetime_amount})"
            
            text += (
                f"👤 <b>User #{user.id}</b>\n"
                f"   Telegram ID: <code>{user.telegram_id}</code>\n"
                f"   Username: @{user.username or 'N/A'}\n"
                f"   Name: {user.full_name or 'N/A'}\n"
                f"   {tier_display}\n"
                f"   Joined: {user.created_at.strftime('%Y-%m-%d') if user.created_at else 'N/A'}\n\n"
            )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Back to Admin Panel", callback_data="admin_back_main")]
        ])
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    
    await callback.answer()


# =====================================================
# VIEW ALL CHANNELS
# =====================================================

@router.callback_query(F.data == "admin_view_channels")
async def view_all_channels(callback: CallbackQuery):
    """Display all channels"""
    async with async_session() as session:
        result = await session.execute(
            select(Channel).order_by(Channel.id)
        )
        channels = result.scalars().all()
        
        if not channels:
            await callback.message.edit_text(
                "❌ No channels found.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 Back", callback_data="admin_back_main")]
                ])
            )
            await callback.answer()
            return
        
        text = "📺 <b>All Channels:</b>\n\n"
        
        for channel in channels:
            visibility = "🔓 Public" if channel.is_public else "🔒 Private"
            status = "✅ Active" if channel.is_active else "❌ Inactive"
            
            # Count active memberships
            membership_count = await session.execute(
                select(func.count(Membership.id))
                .where(Membership.channel_id == channel.id)
                .where(Membership.is_active == True)
            )
            active_members = membership_count.scalar()
            
            text += (
                f"📺 <b>{channel.name}</b>\n"
                f"   ID: {channel.id}\n"
                f"   Chat ID: <code>{channel.telegram_chat_id}</code>\n"
                f"   {visibility} | {status}\n"
                f"   👥 Active Members: {active_members}\n\n"
            )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Back to Admin Panel", callback_data="admin_back_main")]
        ])
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    
    await callback.answer()


# =====================================================
# VIEW RECENT PAYMENTS
# =====================================================

@router.callback_query(F.data == "admin_view_payments")
async def view_payments(callback: CallbackQuery):
    """Display recent payments"""
    async with async_session() as session:
        result = await session.execute(
            select(Payment, User, Channel)
            .join(User, Payment.user_id == User.id)
            .join(Channel, Payment.channel_id == Channel.id)
            .order_by(Payment.created_at.desc())
            .limit(10)
        )
        payments = result.all()
        
        if not payments:
            await callback.message.edit_text(
                "❌ No payments found.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 Back", callback_data="admin_back_main")]
                ])
            )
            await callback.answer()
            return
        
        text = "💰 <b>Recent Payments (Last 10):</b>\n\n"
        
        for payment, user, channel in payments:
            text += (
                f"💳 <b>Payment #{payment.id}</b>\n"
                f"   User: {user.full_name or user.username or user.telegram_id}\n"
                f"   Channel: {channel.name}\n"
                f"   Amount: ₹{payment.amount}\n"
                f"   Status: {payment.status}\n"
                f"   Date: {payment.created_at.strftime('%Y-%m-%d %H:%M') if payment.created_at else 'N/A'}\n\n"
            )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Back to Admin Panel", callback_data="admin_back_main")]
        ])
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    
    await callback.answer()


# =====================================================
# STATISTICS
# =====================================================

@router.callback_query(F.data == "admin_statistics")
async def view_statistics(callback: CallbackQuery):
    """Display bot statistics"""
    async with async_session() as session:
        # Total users
        total_users = await session.execute(select(func.count(User.id)))
        total_users = total_users.scalar()
        
        # Active memberships
        active_memberships = await session.execute(
            select(func.count(Membership.id))
            .where(Membership.is_active == True)
        )
        active_memberships = active_memberships.scalar()
        
        # Total revenue
        total_revenue = await session.execute(
            select(func.sum(Payment.amount))
            .where(Payment.status == "captured")
        )
        total_revenue = total_revenue.scalar() or 0
        
        # Lifetime members
        lifetime_members = await session.execute(
            select(func.count(User.id))
            .where(User.is_lifetime_member == True)
        )
        lifetime_members = lifetime_members.scalar()
        
        # Tier 4 users
        tier4_users = await session.execute(
            select(func.count(User.id))
            .where(User.current_tier == 4)
        )
        tier4_users = tier4_users.scalar()
        
        # Total channels
        total_channels = await session.execute(select(func.count(Channel.id)))
        total_channels = total_channels.scalar()
        
        # Today's revenue
        today = datetime.now(timezone.utc).date()
        today_revenue = await session.execute(
            select(func.sum(Payment.amount))
            .where(Payment.status == "captured")
            .where(func.date(Payment.created_at) == today)
        )
        today_revenue = today_revenue.scalar() or 0
        
        text = (
            f"📊 <b>Bot Statistics</b>\n\n"
            f"👥 Total Users: {total_users}\n"
            f"✅ Active Memberships: {active_memberships}\n"
            f"📺 Total Channels: {total_channels}\n\n"
            f"💰 Total Revenue: ₹{total_revenue:.2f}\n"
            f"💵 Today's Revenue: ₹{today_revenue:.2f}\n\n"
            f"💎 Lifetime Members: {lifetime_members}\n"
            f"🎯 Tier 4 Users: {tier4_users}\n"
        )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Refresh", callback_data="admin_statistics")],
            [InlineKeyboardButton(text="🔙 Back to Admin Panel", callback_data="admin_back_main")]
        ])
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    
    await callback.answer()


# =====================================================
# ADD USER (REDIRECT)
# =====================================================

@router.callback_query(F.data == "admin_add_user")
async def add_user_redirect(callback: CallbackQuery):
    """Redirect to adduser command"""
    await callback.message.edit_text(
        "➕ <b>Add User Manually</b>\n\n"
        "Please use the command: /adduser",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Back", callback_data="admin_back_main")]
        ]),
        parse_mode="HTML"
    )
    await callback.answer()


# =====================================================
# ADD CHANNEL (REDIRECT)
# =====================================================

@router.callback_query(F.data == "admin_add_channel")
async def add_channel_redirect(callback: CallbackQuery):
    """Redirect to addchannel command"""
    await callback.message.edit_text(
        "➕ <b>Add New Channel</b>\n\n"
        "Please use the command: /addchannel",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Back", callback_data="admin_back_main")]
        ]),
        parse_mode="HTML"
    )
    await callback.answer()


# =====================================================
# SEARCH USER (PLACEHOLDER)
# =====================================================

@router.callback_query(F.data == "admin_search_user")
async def search_user(callback: CallbackQuery):
    """Search for a specific user"""
    await callback.message.edit_text(
        "🔍 <b>Search User</b>\n\n"
        "This feature is coming soon!\n"
        "For now, use: /viewuser [telegram_id]",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Back", callback_data="admin_back_main")]
        ]),
        parse_mode="HTML"
    )
    await callback.answer()


# =====================================================
# BACK TO MAIN MENU
# =====================================================

@router.callback_query(F.data == "admin_back_main")
async def back_to_main(callback: CallbackQuery):
    """Return to admin panel main menu"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 View All Users", callback_data="admin_view_users")],
        [InlineKeyboardButton(text="➕ Add User Manually", callback_data="admin_add_user")],
        [InlineKeyboardButton(text="📺 View All Channels", callback_data="admin_view_channels")],
        [InlineKeyboardButton(text="➕ Add New Channel", callback_data="admin_add_channel")],
        [InlineKeyboardButton(text="💰 View Payments", callback_data="admin_view_payments")],
        [InlineKeyboardButton(text="📊 Statistics", callback_data="admin_statistics")],
        [InlineKeyboardButton(text="🔍 Search User", callback_data="admin_search_user")],
        [InlineKeyboardButton(text="🦵 Kick User", callback_data="admin_kick_user")],
        [InlineKeyboardButton(text="📢 Broadcast Message", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="🔗 Send Access Links", callback_data="admin_send_links")],
        [InlineKeyboardButton(text="👤 User Info", callback_data="admin_user_info")],
        [InlineKeyboardButton(text="📥 Import Users CSV", callback_data="admin_import_csv")]

    ])
    
    await callback.message.edit_text(
        "🛠 <b>Admin Panel</b>\n\n"
        "Select an action:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback.answer()

# =====================================================
# SEND ACCESS LINKS TO USER
# =====================================================

@router.callback_query(F.data == "admin_send_links")
async def send_access_links(callback: CallbackQuery):
    await callback.message.edit_text(
        "🔗 <b>Send Access Links</b>\n\n"
        "Use command:\n<code>/sendlinks TELEGRAM_ID</code>\n\n"
        "Example: <code>/sendlinks 123456789</code>\n\n"
        "Bot will generate and send all active membership invite links to that user.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Back", callback_data="admin_back_main")]
        ]),
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(Command("sendlinks"))
async def send_links_command(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    

    if not message.text:
       await message.answer("❌ Please send a valid command.")
       return

    args = message.text.strip().split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Usage: /sendlinks TELEGRAM_ID or /sendlinks ID1,ID2,ID3")
        return

    raw_ids = args[1].split(",")
    telegram_ids = []
    for x in raw_ids:
        x = x.strip()
        if not x.isdigit():
            await message.answer(f"❌ Invalid ID: {x}")
            return
        telegram_ids.append(int(x))

    from backend.bot.bot import bot

    # ── SINGLE USER (existing behavior) ──────────────────
    if len(telegram_ids) == 1:
        target_telegram_id = telegram_ids[0]
        async with async_session() as session:
            user_result = await session.execute(
                select(User).where(User.telegram_id == target_telegram_id)
            )
            user = user_result.scalar_one_or_none()

            if not user:
                await message.answer(f"❌ User {target_telegram_id} not found in DB.")
                return

            memberships_result = await session.execute(
                select(Membership, Channel)
                .join(Channel, Membership.channel_id == Channel.id)
                .where(Membership.user_id == user.id, Membership.is_active == True)
            )
            memberships = memberships_result.all()

            if not memberships:
                await message.answer(f"❌ No active memberships for {target_telegram_id}.")
                return

            success, failed = 0, 0
            for membership, channel in memberships:
                try:
                    invite = await bot.create_chat_invite_link(
                        chat_id=channel.telegram_chat_id,
                        member_limit=1,
                        expire_date=int((datetime.now(timezone.utc) + __import__('datetime').timedelta(hours=24)).timestamp())
                    )
                    await bot.send_message(
                        chat_id=target_telegram_id,
                        text=(
                            f"✅ *Your Access Link*\n\n"
                            f"📺 Channel: *{channel.name}*\n"
                            f"🔗 {invite.invite_link}\n\n"
                            f"_Link expires in 24 hours._"
                        ),
                        parse_mode="Markdown"
                    )
                    success += 1
                except Exception as e:
                    print(f"[SendLinks] Failed for channel {channel.name}: {e}")
                    failed += 1

            await message.answer(
                f"✅ Sent {success} link(s) to user {target_telegram_id}.\n"
                f"❌ Failed: {failed}"
            )

    # ── BATCH USERS ───────────────────────────────────────
    else:
        status_lines = []
        total_success, total_failed = 0, 0

        for telegram_id in telegram_ids:
            async with async_session() as session:
                user_result = await session.execute(
                    select(User).where(User.telegram_id == telegram_id)
                )
                user = user_result.scalar_one_or_none()

                if not user:
                    status_lines.append(f"❌ {telegram_id} — Not found in DB")
                    total_failed += 1
                    continue

                memberships_result = await session.execute(
                    select(Membership, Channel)
                    .join(Channel, Membership.channel_id == Channel.id)
                    .where(Membership.user_id == user.id, Membership.is_active == True)
                )
                rows = memberships_result.all()

                if not rows:
                    status_lines.append(f"❌ {telegram_id} — No active memberships")
                    total_failed += 1
                    continue

                sent, failed = 0, 0
                channel_lines = []
                for membership, channel in rows:
                    try:
                        invite = await bot.create_chat_invite_link(
                            chat_id=channel.telegram_chat_id,
                            member_limit=1,
                            expire_date=int((datetime.now(timezone.utc) + __import__('datetime').timedelta(hours=24)).timestamp())
                        )
                        await bot.send_message(
                            chat_id=telegram_id,
                            text=(
                                f"✅ *Your Access Link*\n\n"
                                f"📺 Channel: *{channel.name}*\n"
                                f"🔗 {invite.invite_link}\n\n"
                                f"_Link expires in 24 hours._"
                            ),
                            parse_mode="Markdown"
                        )
                        sent += 1
                        channel_lines.append(f"   ✅ {channel.name}")
                    except Exception as e:
                        print(f"[SendLinks] Failed for {telegram_id} - {channel.name}: {e}")
                        failed += 1
                        channel_lines.append(f"   ❌ {channel.name}")

                status_lines.append(f"✅ {telegram_id} — Sent {sent}/{sent+failed} link(s)")
                status_lines.extend(channel_lines)
                total_success += 1

        summary = "\n".join(status_lines)
        summary += f"\n\n📊 Done! Success: {total_success} | Failed: {total_failed}"
        await message.answer(summary)

# =====================================================
# USER INFO
# =====================================================

@router.callback_query(F.data == "admin_user_info")
async def user_info_prompt(callback: CallbackQuery):
    await callback.message.edit_text(
        "👤 <b>User Info</b>\n\n"
        "Use command:\n<code>/userinfo TELEGRAM_ID</code>\n\n"
        "Example: <code>/userinfo 123456789</code>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Back", callback_data="admin_back_main")]
        ]),
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(Command("userinfo"))
async def user_info_command(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return

    parts = message.text.strip().split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Usage: /userinfo TELEGRAM_ID")
        return

    target_id = int(parts[1])

    async with async_session() as session:
        user_result = await session.execute(
            select(User).where(User.telegram_id == target_id)
        )
        user = user_result.scalar_one_or_none()

        if not user:
            await message.answer(f"❌ User {target_id} not found in DB.")
            return

        # Get all memberships
        memberships_result = await session.execute(
            select(Membership, Channel)
            .join(Channel, Membership.channel_id == Channel.id)
            .where(Membership.user_id == user.id)
            .order_by(Membership.is_active.desc(), Membership.expiry_date.desc())
        )
        memberships = memberships_result.all()

        # Get total payments
        payments_result = await session.execute(
            select(func.sum(Payment.amount), func.count(Payment.id))
            .where(Payment.user_id == user.id, Payment.status == "captured")
        )
        total_paid, total_payments = payments_result.one()
        total_paid = total_paid or 0

        # Build text
        username = f"@{user.username}" if user.username else "No username"
        joined = user.created_at.strftime('%d %b %Y') if user.created_at else "N/A"

        text = (
            f"👤 <b>User Info</b>\n"
            f"━━━━━━━━━━━━━━━\n"
            f"🆔 Telegram ID: <code>{user.telegram_id}</code>\n"
            f"👤 Name: {user.full_name or 'N/A'}\n"
            f"📛 Username: {username}\n"
            f"📅 Joined: {joined}\n"
            f"🎯 Tier: {user.current_tier}\n"
            f"💰 Highest Paid: ₹{float(user.highest_amount_paid or 0):.0f}\n"
            f"💳 Total Paid: ₹{float(total_paid):.0f} ({total_payments} payments)\n"
            f"━━━━━━━━━━━━━━━\n\n"
        )

        active_memberships = []
        expired_memberships = []

        for membership, channel in memberships:
            expiry = membership.expiry_date.strftime('%d %b %Y') if membership.expiry_date else "N/A"
            if membership.is_active:
                text += f"✅ <b>{channel.name}</b>\n"
                text += f"   Expires: {expiry}\n"
                text += f"   Plan: {membership.validity_days} days | ₹{membership.amount_paid}\n\n"
                active_memberships.append((membership, channel))
            else:
                text += f"❌ <b>{channel.name}</b>\n"
                text += f"   Expired: {expiry}\n\n"
                expired_memberships.append((membership, channel))

        if not memberships:
            text += "📭 No memberships found.\n"

        # Build invite link buttons for active memberships only
        keyboard = []
        for membership, channel in active_memberships:
            keyboard.append([
                InlineKeyboardButton(
                    text=f"🔗 Send Link — {channel.name}",
                    callback_data=f"send_one_link:{user.telegram_id}:{channel.telegram_chat_id}:{channel.id}"
                )
            ])
        keyboard.append([
            InlineKeyboardButton(text="🔙 Back", callback_data="admin_back_main")
        ])

        await message.answer(
            text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
            parse_mode="HTML"
        )


@router.callback_query(F.data.startswith("send_one_link:"))
async def send_one_link(callback: CallbackQuery):
    from backend.bot.bot import bot
    from datetime import timedelta

    parts = callback.data.split(":")
    target_telegram_id = int(parts[1])
    chat_id = int(parts[2])
    channel_id = int(parts[3])

    async with async_session() as session:
        channel = await session.get(Channel, channel_id)

    try:
        invite = await bot.create_chat_invite_link(
            chat_id=chat_id,
            member_limit=1,
            expire_date=int((datetime.now(timezone.utc) + timedelta(hours=24)).timestamp())
        )
        await bot.send_message(
            chat_id=target_telegram_id,
            text=(
                f"✅ *Your Access Link*\n\n"
                f"📺 Channel: *{channel.name}*\n"
                f"🔗 {invite.invite_link}\n\n"
                f"_Link expires in 24 hours._"
            ),
            parse_mode="Markdown"
        )
        await callback.answer(f"✅ Link sent for {channel.name}!")
    except Exception as e:
        print(f"[UserInfo] Send link failed: {e}")
        await callback.answer(f"❌ Failed: {e}", show_alert=True)

# =====================================================
# CSV IMPORT USERS
# =====================================================

@router.callback_query(F.data == "admin_import_csv")
async def import_csv_prompt(callback: CallbackQuery):
    await callback.message.edit_text(
        "📥 <b>Import Users via CSV</b>\n\n"
        "Send a <b>.csv file</b> with this exact format:\n\n"
        "<code>telegram_id,name,channel_id,validity_days,amount,start_date,expiry_date</code>\n\n"
        "Example:\n"
        "<code>1030866345,PK,12,548,599,2026-03-21,2027-09-20</code>\n"
        "<code>1441405972,A,13,999,399,2026-03-06,2028-11-29</code>\n\n"
        "📌 Date format: <b>YYYY-MM-DD</b>\n"
        "📌 Send the file directly in this chat\n"
        "📌 Bot will import all rows and send invite links automatically",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Back", callback_data="admin_back_main")]
        ]),
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(F.document)
async def handle_csv_import(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return

    if not message.document.file_name.endswith(".csv"):
        return

    from backend.bot.bot import bot
    from datetime import timedelta
    import csv
    import io

    await message.answer("⏳ Processing CSV... please wait.")

    # Download file
    try:
        file = await bot.get_file(message.document.file_id)
        file_bytes = await bot.download_file(file.file_path)
        content = file_bytes.read().decode("utf-8")
    except Exception as e:
        await message.answer(f"❌ Failed to download file: {e}")
        return

    reader = csv.DictReader(io.StringIO(content))

    success_lines = []
    skipped_lines = []
    failed_lines = []
    failed_csv_rows = []

    total_rows = 0

    for row in reader:
        total_rows += 1
        try:
            telegram_id = int(row["telegram_id"].strip())
            name = row["name"].strip()
            channel_id = int(row["channel_id"].strip())
            validity_days = int(row["validity_days"].strip())
            amount = int(row["amount"].strip())
            start_date = datetime.strptime(row["start_date"].strip(), "%Y-%m-%d")
            expiry_date = datetime.strptime(row["expiry_date"].strip(), "%Y-%m-%d")
            is_active = expiry_date.date() >= datetime.now(timezone.utc).date()
        except Exception as e:
            failed_lines.append(f"❌ Row error: {row} — {e}")
            failed_csv_rows.append(row)
            continue

        async with async_session() as session:
            # Upsert user
            user_result = await session.execute(
                select(User).where(User.telegram_id == telegram_id)
            )
            user = user_result.scalar_one_or_none()

            if not user:
                # Auto tier based on amount
                if amount >= 1499:
                    tier = 4
                elif amount >= 999:
                    tier = 3
                elif amount >= 499:
                    tier = 2
                else:
                    tier = 1

                user = User(
                    telegram_id=telegram_id,
                    full_name=name,
                    current_tier=tier,
                    highest_amount_paid=amount
                )
                session.add(user)
                await session.flush()
            else:
                if amount > float(user.highest_amount_paid or 0):
                    user.highest_amount_paid = amount

            # Check duplicate membership
            existing = await session.execute(
                select(Membership).where(
                    Membership.user_id == user.id,
                    Membership.channel_id == channel_id,
                    Membership.is_active == True
                )
            )
            existing = existing.scalar_one_or_none()

            channel = await session.get(Channel, channel_id)
            channel_name = channel.name if channel else f"Channel {channel_id}"

            if existing:
                skipped_lines.append(
                    f"⚠️ {name} ({telegram_id})\n"
                    f"   {channel_name} — already has active membership"
                )
                await session.commit()
                continue

            # Insert membership
            session.add(Membership(
                user_id=user.id,
                channel_id=channel_id,
                validity_days=validity_days,
                amount_paid=amount,
                start_date=start_date,
                expiry_date=expiry_date,
                is_active=is_active
            ))
            await session.commit()

            # Send invite link
            if is_active and channel:
                try:
                    invite = await bot.create_chat_invite_link(
                        chat_id=channel.telegram_chat_id,
                        member_limit=1,
                        expire_date=int((datetime.now(timezone.utc) + timedelta(hours=24)).timestamp())
                    )
                    await bot.send_message(
                        chat_id=telegram_id,
                        text=(
                            f"✅ *Your Access Link*\n\n"
                            f"📺 Channel: *{channel_name}*\n"
                            f"🔗 {invite.invite_link}\n\n"
                            f"_Link expires in 24 hours._"
                        ),
                        parse_mode="Markdown"
                    )
                    success_lines.append(
                        f"✅ {name} ({telegram_id})\n"
                        f"   {channel_name} — ✅ Link Sent"
                    )
                except Exception as e:
                    failed_lines.append(
                        f"❌ {name} ({telegram_id})\n"
                        f"   {channel_name} — {str(e)}"
                    )
                    failed_csv_rows.append(row)
            else:
                success_lines.append(
                    f"✅ {name} ({telegram_id})\n"
                    f"   {channel_name} — Added (expired, no link sent)"
                )

    # Build report
    report = "📊 <b>CSV Import Report</b>\n━━━━━━━━━━━━━━━\n\n"

    if success_lines:
        report += "✅ <b>SUCCESSFULLY ADDED &amp; LINK SENT</b>\n"
        report += "\n".join(success_lines) + "\n\n"

    if skipped_lines:
        report += "⚠️ <b>ALREADY EXISTS (Skipped)</b>\n"
        report += "\n".join(skipped_lines) + "\n\n"

    if failed_lines:
        report += "❌ <b>FAILED</b>\n"
        report += "\n".join(failed_lines) + "\n\n"

    report += (
        f"━━━━━━━━━━━━━━━\n"
        f"📈 Total Rows: {total_rows}\n"
        f"✅ Success: {len(success_lines)}\n"
        f"⚠️ Skipped: {len(skipped_lines)}\n"
        f"❌ Failed: {len(failed_lines)}\n"
        f"🔗 Links Sent: {len([l for l in success_lines if 'Link Sent' in l])}"
    )

    await message.answer(report, parse_mode="HTML")

    # Send failed CSV if any
    if failed_csv_rows:
        failed_content = "telegram_id,name,channel_id,validity_days,amount,start_date,expiry_date\n"
        for r in failed_csv_rows:
            failed_content += ",".join([
                str(r.get("telegram_id", "")),
                str(r.get("name", "")),
                str(r.get("channel_id", "")),
                str(r.get("validity_days", "")),
                str(r.get("amount", "")),
                str(r.get("start_date", "")),
                str(r.get("expiry_date", ""))
            ]) + "\n"

        failed_bytes = io.BytesIO(failed_content.encode("utf-8"))
        failed_bytes.name = "failed_users.csv"

        from aiogram.types import BufferedInputFile
        await message.answer_document(
            document=BufferedInputFile(failed_bytes.getvalue(), filename="failed_users.csv"),
            caption="❌ These users failed — fix and re-import"
        )