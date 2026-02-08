import os
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, func, and_, extract
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from backend.app.db.session import async_session
from backend.app.db.models import User, Channel, Membership, Payment

router = Router()

ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x]


# =====================================================
# HELPER FUNCTIONS
# =====================================================

async def get_revenue_stats(start_date=None, end_date=None):
    """Get revenue statistics for a date range"""
    async with async_session() as session:
        # Base query
        query = select(func.sum(Payment.amount)).where(Payment.status == "captured")
        
        if start_date:
            query = query.where(Payment.created_at >= start_date)
        if end_date:
            query = query.where(Payment.created_at <= end_date)
        
        result = await session.execute(query)
        total = result.scalar() or 0
        
        # Count of payments
        count_query = select(func.count(Payment.id)).where(Payment.status == "captured")
        if start_date:
            count_query = count_query.where(Payment.created_at >= start_date)
        if end_date:
            count_query = count_query.where(Payment.created_at <= end_date)
        
        count_result = await session.execute(count_query)
        count = count_result.scalar() or 0
        
        return {"total": float(total), "count": count}


async def get_membership_stats():
    """Get active vs expired membership counts"""
    async with async_session() as session:
        now = datetime.now(timezone.utc)
        
        # Active memberships
        active_query = select(func.count(Membership.id)).where(
            Membership.is_active == True,
            Membership.expiry_date > now
        )
        active_result = await session.execute(active_query)
        active_count = active_result.scalar() or 0
        
        # Expired memberships
        expired_query = select(func.count(Membership.id)).where(
            and_(
                Membership.expiry_date <= now,
                Membership.is_active == False
            )
        )
        expired_result = await session.execute(expired_query)
        expired_count = expired_result.scalar() or 0
        
        # Total memberships ever created
        total_query = select(func.count(Membership.id))
        total_result = await session.execute(total_query)
        total_count = total_result.scalar() or 0
        
        return {
            "active": active_count,
            "expired": expired_count,
            "total": total_count
        }


async def get_channel_breakdown():
    """Get revenue and member count per channel"""
    async with async_session() as session:
        # Revenue per channel
        query = (
            select(
                Channel.name,
                func.sum(Payment.amount).label("revenue"),
                func.count(Payment.id).label("payment_count")
            )
            .join(Payment, Payment.channel_id == Channel.id)
            .where(Payment.status == "captured")
            .group_by(Channel.id, Channel.name)
            .order_by(func.sum(Payment.amount).desc())
        )
        
        result = await session.execute(query)
        channels = result.all()
        
        # Active members per channel
        now = datetime.now(timezone.utc)
        members_query = (
            select(
                Channel.name,
                func.count(Membership.id).label("active_members")
            )
            .join(Membership, Membership.channel_id == Channel.id)
            .where(
                Membership.is_active == True,
                Membership.expiry_date > now
            )
            .group_by(Channel.id, Channel.name)
        )
        
        members_result = await session.execute(members_query)
        members_dict = {row[0]: row[1] for row in members_result.all()}
        
        # Combine data
        breakdown = []
        for channel_name, revenue, payment_count in channels:
            breakdown.append({
                "name": channel_name,
                "revenue": float(revenue or 0),
                "payments": payment_count,
                "active_members": members_dict.get(channel_name, 0)
            })
        
        return breakdown


async def get_user_growth_stats():
    """Get user registration trends"""
    async with async_session() as session:
        # Total users
        total_query = select(func.count(User.id))
        total_result = await session.execute(total_query)
        total_users = total_result.scalar() or 0
        
        # Users registered today
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        today_query = select(func.count(User.id)).where(User.created_at >= today_start)
        today_result = await session.execute(today_query)
        today_users = today_result.scalar() or 0
        
        # Users registered this month
        month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        month_query = select(func.count(User.id)).where(User.created_at >= month_start)
        month_result = await session.execute(month_query)
        month_users = month_result.scalar() or 0
        
        return {
            "total": total_users,
            "today": today_users,
            "this_month": month_users
        }


async def get_payment_success_rate(days=30):
    """Calculate payment success rate (captured vs total)"""
    async with async_session() as session:
        start_date = datetime.now(timezone.utc) - timedelta(days=days)
        
        # Total payments attempted
        total_query = select(func.count(Payment.id)).where(Payment.created_at >= start_date)
        total_result = await session.execute(total_query)
        total = total_result.scalar() or 0
        
        # Successful payments
        success_query = select(func.count(Payment.id)).where(
            Payment.created_at >= start_date,
            Payment.status == "captured"
        )
        success_result = await session.execute(success_query)
        success = success_result.scalar() or 0
        
        rate = (success / total * 100) if total > 0 else 0
        
        return {
            "total": total,
            "success": success,
            "rate": round(rate, 1)
        }


async def get_monthly_revenue_trend(months=6):
    """Get revenue for last N months"""
    async with async_session() as session:
        now = datetime.now(timezone.utc)
        
        monthly_data = []
        
        for i in range(months - 1, -1, -1):
            # Calculate month start
            month_date = now - timedelta(days=30 * i)
            month_start = month_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            
            # Calculate next month start
            if month_start.month == 12:
                next_month = month_start.replace(year=month_start.year + 1, month=1)
            else:
                next_month = month_start.replace(month=month_start.month + 1)
            
            # Query revenue
            query = select(func.sum(Payment.amount)).where(
                Payment.status == "captured",
                Payment.created_at >= month_start,
                Payment.created_at < next_month
            )
            
            result = await session.execute(query)
            revenue = result.scalar() or 0
            
            monthly_data.append({
                "month": month_start.strftime("%b %Y"),
                "revenue": float(revenue)
            })
        
        return monthly_data


# =====================================================
# STATS COMMAND HANDLERS
# =====================================================

@router.message(Command("stats"))
async def stats_command(message: Message):
    """Main stats command - shows menu"""
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔ This command is for admins only.")
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📊 Overview", callback_data="stats_overview"),
            InlineKeyboardButton(text="💰 Revenue", callback_data="stats_revenue")
        ],
        [
            InlineKeyboardButton(text="👥 Members", callback_data="stats_members"),
            InlineKeyboardButton(text="📺 Channels", callback_data="stats_channels")
        ],
        [
            InlineKeyboardButton(text="📈 Growth", callback_data="stats_growth"),
            InlineKeyboardButton(text="📅 Monthly Trend", callback_data="stats_trend")
        ]
    ])
    
    await message.answer(
        "📊 <b>Analytics Dashboard</b>\n\n"
        "Select a report to view:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


@router.callback_query(F.data == "stats_overview")
async def stats_overview(callback: CallbackQuery):
    """Comprehensive overview of all stats"""
    await callback.message.edit_text("⏳ Loading analytics...")
    
    # Gather all stats
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    # Revenue stats
    total_revenue = await get_revenue_stats()
    today_revenue = await get_revenue_stats(start_date=today_start)
    month_revenue = await get_revenue_stats(start_date=month_start)
    
    # Membership stats
    membership_stats = await get_membership_stats()
    
    # User growth
    user_stats = await get_user_growth_stats()
    
    # Payment success rate
    success_stats = await get_payment_success_rate(days=30)
    
    text = (
        "📊 <b>Complete Analytics Overview</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        "💰 <b>REVENUE</b>\n"
        f"├ All Time: ₹{total_revenue['total']:,.2f}\n"
        f"├ This Month: ₹{month_revenue['total']:,.2f}\n"
        f"└ Today: ₹{today_revenue['total']:,.2f}\n\n"
        
        "👥 <b>MEMBERSHIPS</b>\n"
        f"├ Active: {membership_stats['active']}\n"
        f"├ Expired: {membership_stats['expired']}\n"
        f"└ Total: {membership_stats['total']}\n\n"
        
        "📈 <b>USERS</b>\n"
        f"├ Total: {user_stats['total']}\n"
        f"├ This Month: {user_stats['this_month']}\n"
        f"└ Today: {user_stats['today']}\n\n"
        
        "✅ <b>PAYMENT SUCCESS (30 days)</b>\n"
        f"├ Success Rate: {success_stats['rate']}%\n"
        f"├ Successful: {success_stats['success']}\n"
        f"└ Total: {success_stats['total']}\n\n"
        
        f"🕐 Generated: {now.strftime('%d %b %Y, %I:%M %p')}"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Back to Menu", callback_data="stats_menu")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "stats_revenue")
async def stats_revenue(callback: CallbackQuery):
    """Detailed revenue breakdown"""
    await callback.message.edit_text("⏳ Loading revenue data...")
    
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = now - timedelta(days=7)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    total_revenue = await get_revenue_stats()
    today_revenue = await get_revenue_stats(start_date=today_start)
    week_revenue = await get_revenue_stats(start_date=week_start)
    month_revenue = await get_revenue_stats(start_date=month_start)
    
    text = (
        "💰 <b>Revenue Analytics</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        f"📅 <b>TODAY</b>\n"
        f"├ Revenue: ₹{today_revenue['total']:,.2f}\n"
        f"└ Payments: {today_revenue['count']}\n\n"
        
        f"📅 <b>LAST 7 DAYS</b>\n"
        f"├ Revenue: ₹{week_revenue['total']:,.2f}\n"
        f"└ Payments: {week_revenue['count']}\n\n"
        
        f"📅 <b>THIS MONTH</b>\n"
        f"├ Revenue: ₹{month_revenue['total']:,.2f}\n"
        f"└ Payments: {month_revenue['count']}\n\n"
        
        f"📅 <b>ALL TIME</b>\n"
        f"├ Revenue: ₹{total_revenue['total']:,.2f}\n"
        f"└ Payments: {total_revenue['count']}\n\n"
    )
    
    # Calculate averages
    if total_revenue['count'] > 0:
        avg_payment = total_revenue['total'] / total_revenue['count']
        text += f"💵 <b>Average Payment:</b> ₹{avg_payment:,.2f}\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Back to Menu", callback_data="stats_menu")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "stats_members")
async def stats_members(callback: CallbackQuery):
    """Member statistics"""
    await callback.message.edit_text("⏳ Loading member data...")
    
    membership_stats = await get_membership_stats()
    
    active = membership_stats['active']
    expired = membership_stats['expired']
    total = membership_stats['total']
    
    retention_rate = (active / total * 100) if total > 0 else 0
    churn_rate = (expired / total * 100) if total > 0 else 0
    
    text = (
        "👥 <b>Membership Analytics</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        f"✅ <b>Active Members:</b> {active}\n"
        f"❌ <b>Expired Members:</b> {expired}\n"
        f"📊 <b>Total Memberships:</b> {total}\n\n"
        
        f"📈 <b>Retention Rate:</b> {retention_rate:.1f}%\n"
        f"📉 <b>Churn Rate:</b> {churn_rate:.1f}%\n"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Back to Menu", callback_data="stats_menu")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "stats_channels")
async def stats_channels(callback: CallbackQuery):
    """Channel-wise breakdown"""
    await callback.message.edit_text("⏳ Loading channel data...")
    
    channels = await get_channel_breakdown()
    
    if not channels:
        text = "📺 <b>Channel Breakdown</b>\n\nNo channels with revenue yet."
    else:
        text = (
            "📺 <b>Channel Performance</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        )
        
        for i, channel in enumerate(channels, 1):
            text += (
                f"{i}. <b>{channel['name']}</b>\n"
                f"   💰 Revenue: ₹{channel['revenue']:,.2f}\n"
                f"   💳 Payments: {channel['payments']}\n"
                f"   👥 Active: {channel['active_members']}\n\n"
            )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Back to Menu", callback_data="stats_menu")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "stats_growth")
async def stats_growth(callback: CallbackQuery):
    """User growth statistics"""
    await callback.message.edit_text("⏳ Loading growth data...")
    
    user_stats = await get_user_growth_stats()
    
    text = (
        "📈 <b>User Growth</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        f"👤 <b>Total Users:</b> {user_stats['total']}\n"
        f"📅 <b>This Month:</b> {user_stats['this_month']}\n"
        f"🆕 <b>Today:</b> {user_stats['today']}\n\n"
    )
    
    # Calculate growth rate
    if user_stats['total'] > 0:
        month_growth_pct = (user_stats['this_month'] / user_stats['total'] * 100)
        text += f"📊 <b>Monthly Growth:</b> {month_growth_pct:.1f}% of user base\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Back to Menu", callback_data="stats_menu")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "stats_trend")
async def stats_trend(callback: CallbackQuery):
    """Monthly revenue trend"""
    await callback.message.edit_text("⏳ Loading trend data...")
    
    trend_data = await get_monthly_revenue_trend(months=6)
    
    text = (
        "📅 <b>6-Month Revenue Trend</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    )
    
    for month_data in trend_data:
        # Create simple bar chart
        bar_length = int(month_data['revenue'] / 100)  # 1 block per ₹100
        bar = "▓" * min(bar_length, 20)  # Max 20 blocks
        
        text += (
            f"<b>{month_data['month']}</b>\n"
            f"{bar} ₹{month_data['revenue']:,.2f}\n\n"
        )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Back to Menu", callback_data="stats_menu")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "stats_menu")
async def stats_menu(callback: CallbackQuery):
    """Return to main stats menu"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📊 Overview", callback_data="stats_overview"),
            InlineKeyboardButton(text="💰 Revenue", callback_data="stats_revenue")
        ],
        [
            InlineKeyboardButton(text="👥 Members", callback_data="stats_members"),
            InlineKeyboardButton(text="📺 Channels", callback_data="stats_channels")
        ],
        [
            InlineKeyboardButton(text="📈 Growth", callback_data="stats_growth"),
            InlineKeyboardButton(text="📅 Monthly Trend", callback_data="stats_trend")
        ]
    ])
    
    await callback.message.edit_text(
        "📊 <b>Analytics Dashboard</b>\n\n"
        "Select a report to view:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback.answer()