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
        [InlineKeyboardButton(text="➕ Add New Channel", callback_data="admin_add_channel")],
        [InlineKeyboardButton(text="💰 View Payments", callback_data="admin_view_payments")],
        [InlineKeyboardButton(text="📊 Statistics", callback_data="admin_statistics")],
        [InlineKeyboardButton(text="🔍 Search User", callback_data="admin_search_user")]
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
        [InlineKeyboardButton(text="🔍 Search User", callback_data="admin_search_user")]
    ])
    
    await callback.message.edit_text(
        "🛠 <b>Admin Panel</b>\n\n"
        "Select an action:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback.answer()