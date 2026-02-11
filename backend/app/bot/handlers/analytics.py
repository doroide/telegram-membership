import os
from datetime import datetime, timezone, timedelta
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from sqlalchemy import select, func, and_, extract
from sqlalchemy.orm import selectinload

from backend.app.db.session import async_session
from backend.app.db.models import User, Channel, Membership, Payment

router = Router()

ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x]


# =====================================================
# MAIN ANALYTICS COMMAND
# =====================================================

@router.message(Command("analytics"))
async def analytics_command(message: Message):
    """Show analytics dashboard"""
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔ This command is for admins only.")
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📈 Overview", callback_data="analytics_overview")],
        [InlineKeyboardButton(text="💰 Revenue Reports", callback_data="analytics_revenue")],
        [InlineKeyboardButton(text="📺 Channel Performance", callback_data="analytics_channels")],
        [InlineKeyboardButton(text="👥 User Growth", callback_data="analytics_users")],
        [InlineKeyboardButton(text="🎯 Popular Plans", callback_data="analytics_plans")],
        [InlineKeyboardButton(text="📊 Conversion Rates", callback_data="analytics_conversion")]
    ])
    
    await message.answer(
        "📊 <b>Analytics Dashboard</b>\n\n"
        "Select a report to view:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


# =====================================================
# OVERVIEW
# =====================================================

@router.callback_query(F.data == "analytics_overview")
async def analytics_overview(callback: CallbackQuery):
    """Show overall statistics overview"""
    async with async_session() as session:
        now = datetime.now(timezone.utc)
        today = now.date()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        
        # Total users
        total_users = await session.execute(select(func.count(User.id)))
        total_users = total_users.scalar()
        
        # Users this week
        week_users = await session.execute(
            select(func.count(User.id))
            .where(func.date(User.created_at) >= week_ago)
        )
        week_users = week_users.scalar()
        
        # Active memberships
        active_memberships = await session.execute(
            select(func.count(Membership.id))
            .where(Membership.is_active == True)
        )
        active_memberships = active_memberships.scalar()
        
        # Total revenue all time
        total_revenue = await session.execute(
            select(func.sum(Payment.amount))
            .where(Payment.status == "captured")
        )
        total_revenue = total_revenue.scalar() or 0
        
        # Revenue this month
        month_revenue = await session.execute(
            select(func.sum(Payment.amount))
            .where(
                Payment.status == "captured",
                func.date(Payment.created_at) >= month_ago
            )
        )
        month_revenue = month_revenue.scalar() or 0
        
        # Revenue today
        today_revenue = await session.execute(
            select(func.sum(Payment.amount))
            .where(
                Payment.status == "captured",
                func.date(Payment.created_at) == today
            )
        )
        today_revenue = today_revenue.scalar() or 0
        
        # Average revenue per user
        arpu = total_revenue / total_users if total_users > 0 else 0
        
        # Lifetime members
        lifetime_members = await session.execute(
            select(func.count(User.id))
            .where(User.is_lifetime_member == True)
        )
        lifetime_members = lifetime_members.scalar()
        
        # Tier distribution
        tier1 = await session.execute(select(func.count(User.id)).where(User.current_tier == 1))
        tier2 = await session.execute(select(func.count(User.id)).where(User.current_tier == 2))
        tier3 = await session.execute(select(func.count(User.id)).where(User.current_tier == 3))
        tier4 = await session.execute(select(func.count(User.id)).where(User.current_tier == 4))
        
        tier1 = tier1.scalar()
        tier2 = tier2.scalar()
        tier3 = tier3.scalar()
        tier4 = tier4.scalar()
        
        text = (
            f"📊 <b>Analytics Overview</b>\n\n"
            f"<b>💰 Revenue:</b>\n"
            f"├ Today: ₹{today_revenue:.2f}\n"
            f"├ This Month: ₹{month_revenue:.2f}\n"
            f"├ All Time: ₹{total_revenue:.2f}\n"
            f"└ ARPU: ₹{arpu:.2f}\n\n"
            f"<b>👥 Users:</b>\n"
            f"├ Total: {total_users}\n"
            f"├ This Week: +{week_users}\n"
            f"└ Active Subs: {active_memberships}\n\n"
            f"<b>💎 Tier Distribution:</b>\n"
            f"├ Tier 1: {tier1} ({tier1/total_users*100:.1f}%)\n"
            f"├ Tier 2: {tier2} ({tier2/total_users*100:.1f}%)\n"
            f"├ Tier 3: {tier3} ({tier3/total_users*100:.1f}%)\n"
            f"├ Tier 4: {tier4} ({tier4/total_users*100:.1f}%)\n"
            f"└ Lifetime: {lifetime_members}\n"
        )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Refresh", callback_data="analytics_overview")],
            [InlineKeyboardButton(text="🔙 Back", callback_data="analytics_back")]
        ])
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    
    await callback.answer()


# =====================================================
# REVENUE REPORTS
# =====================================================

@router.callback_query(F.data == "analytics_revenue")
async def analytics_revenue(callback: CallbackQuery):
    """Show detailed revenue breakdown"""
    async with async_session() as session:
        now = datetime.now(timezone.utc)
        today = now.date()
        
        # Get revenue for last 30 days
        revenue_data = []
        for i in range(30, -1, -1):
            date = today - timedelta(days=i)
            daily_revenue = await session.execute(
                select(func.sum(Payment.amount))
                .where(
                    Payment.status == "captured",
                    func.date(Payment.created_at) == date
                )
            )
            revenue = daily_revenue.scalar() or 0
            revenue_data.append((date, revenue))
        
        # Calculate trends
        last_7_days = sum(r for _, r in revenue_data[-7:])
        prev_7_days = sum(r for _, r in revenue_data[-14:-7])
        growth = ((last_7_days - prev_7_days) / prev_7_days * 100) if prev_7_days > 0 else 0
        
        # Build chart (simple text-based)
        text = f"💰 <b>Revenue Report (Last 30 Days)</b>\n\n"
        
        # Show last 7 days in detail
        text += "<b>📅 Last 7 Days:</b>\n"
        for date, revenue in revenue_data[-7:]:
            bar_length = int(revenue / 100) if revenue > 0 else 0
            bar = "█" * min(bar_length, 20)
            text += f"{date.strftime('%d %b')}: ₹{revenue:.0f} {bar}\n"
        
        text += f"\n<b>📈 Weekly Comparison:</b>\n"
        text += f"├ Last 7 days: ₹{last_7_days:.2f}\n"
        text += f"├ Previous 7 days: ₹{prev_7_days:.2f}\n"
        
        if growth > 0:
            text += f"└ Growth: +{growth:.1f}% 📈\n"
        elif growth < 0:
            text += f"└ Growth: {growth:.1f}% 📉\n"
        else:
            text += f"└ Growth: 0% ➡️\n"
        
        # Monthly stats
        total_month = sum(r for _, r in revenue_data)
        avg_daily = total_month / 30
        
        text += f"\n<b>📊 30-Day Summary:</b>\n"
        text += f"├ Total: ₹{total_month:.2f}\n"
        text += f"└ Avg/Day: ₹{avg_daily:.2f}\n"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Refresh", callback_data="analytics_revenue")],
            [InlineKeyboardButton(text="🔙 Back", callback_data="analytics_back")]
        ])
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    
    await callback.answer()


# =====================================================
# CHANNEL PERFORMANCE
# =====================================================

@router.callback_query(F.data == "analytics_channels")
async def analytics_channels(callback: CallbackQuery):
    """Show channel-wise performance"""
    async with async_session() as session:
        # Get all channels
        channels_result = await session.execute(
            select(Channel).order_by(Channel.id)
        )
        channels = channels_result.scalars().all()
        
        text = "📺 <b>Channel Performance</b>\n\n"
        
        total_revenue_all = 0
        total_members_all = 0
        
        for channel in channels:
            # Active members
            active_members = await session.execute(
                select(func.count(Membership.id))
                .where(
                    Membership.channel_id == channel.id,
                    Membership.is_active == True
                )
            )
            active_members = active_members.scalar()
            
            # Total members (ever)
            total_members = await session.execute(
                select(func.count(Membership.id))
                .where(Membership.channel_id == channel.id)
            )
            total_members = total_members.scalar()
            
            # Revenue from this channel
            channel_revenue = await session.execute(
                select(func.sum(Payment.amount))
                .where(
                    Payment.channel_id == channel.id,
                    Payment.status == "captured"
                )
            )
            channel_revenue = channel_revenue.scalar() or 0
            
            # Average revenue per member
            avg_rev = channel_revenue / total_members if total_members > 0 else 0
            
            total_revenue_all += channel_revenue
            total_members_all += active_members
            
            visibility = "🔓" if channel.is_public else "🔒"
            
            text += (
                f"{visibility} <b>{channel.name}</b>\n"
                f"├ Active: {active_members} | Total: {total_members}\n"
                f"├ Revenue: ₹{channel_revenue:.2f}\n"
                f"└ Avg/User: ₹{avg_rev:.2f}\n\n"
            )
        
        text += (
            f"<b>📊 Overall:</b>\n"
            f"├ Total Active Members: {total_members_all}\n"
            f"└ Total Revenue: ₹{total_revenue_all:.2f}\n"
        )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Refresh", callback_data="analytics_channels")],
            [InlineKeyboardButton(text="🔙 Back", callback_data="analytics_back")]
        ])
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    
    await callback.answer()


# =====================================================
# USER GROWTH
# =====================================================

@router.callback_query(F.data == "analytics_users")
async def analytics_users(callback: CallbackQuery):
    """Show user growth trends"""
    async with async_session() as session:
        now = datetime.now(timezone.utc)
        today = now.date()
        
        # User signups for last 30 days
        signup_data = []
        for i in range(30, -1, -1):
            date = today - timedelta(days=i)
            daily_signups = await session.execute(
                select(func.count(User.id))
                .where(func.date(User.created_at) == date)
            )
            signups = daily_signups.scalar()
            signup_data.append((date, signups))
        
        # Calculate trends
        last_7_signups = sum(s for _, s in signup_data[-7:])
        prev_7_signups = sum(s for _, s in signup_data[-14:-7])
        growth = ((last_7_signups - prev_7_signups) / prev_7_signups * 100) if prev_7_signups > 0 else 0
        
        text = f"👥 <b>User Growth Report</b>\n\n"
        
        # Show last 7 days
        text += "<b>📅 Last 7 Days:</b>\n"
        for date, signups in signup_data[-7:]:
            bar = "█" * signups if signups > 0 else ""
            text += f"{date.strftime('%d %b')}: {signups} users {bar}\n"
        
        text += f"\n<b>📈 Weekly Comparison:</b>\n"
        text += f"├ Last 7 days: {last_7_signups} users\n"
        text += f"├ Previous 7 days: {prev_7_signups} users\n"
        
        if growth > 0:
            text += f"└ Growth: +{growth:.1f}% 📈\n"
        elif growth < 0:
            text += f"└ Growth: {growth:.1f}% 📉\n"
        else:
            text += f"└ Growth: 0% ➡️\n"
        
        # Total stats
        total_signups = sum(s for _, s in signup_data)
        avg_daily = total_signups / 30
        
        # Total users
        total_users = await session.execute(select(func.count(User.id)))
        total_users = total_users.scalar()
        
        # Active vs inactive
        active_users = await session.execute(
            select(func.count(User.id.distinct()))
            .select_from(User)
            .join(Membership)
            .where(Membership.is_active == True)
        )
        active_users = active_users.scalar()
        
        inactive_users = total_users - active_users
        activation_rate = (active_users / total_users * 100) if total_users > 0 else 0
        
        text += (
            f"\n<b>📊 30-Day Summary:</b>\n"
            f"├ New Signups: {total_signups}\n"
            f"└ Avg/Day: {avg_daily:.1f}\n\n"
            f"<b>👥 User Base:</b>\n"
            f"├ Total: {total_users}\n"
            f"├ Active: {active_users} ({activation_rate:.1f}%)\n"
            f"└ Inactive: {inactive_users}\n"
        )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Refresh", callback_data="analytics_users")],
            [InlineKeyboardButton(text="🔙 Back", callback_data="analytics_back")]
        ])
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    
    await callback.answer()


# =====================================================
# POPULAR PLANS
# =====================================================

@router.callback_query(F.data == "analytics_plans")
async def analytics_plans(callback: CallbackQuery):
    """Show most popular subscription plans"""
    async with async_session() as session:
        # Group by validity_days and tier
        plan_stats = await session.execute(
            select(
                Membership.validity_days,
                Membership.tier,
                func.count(Membership.id).label('count'),
                func.sum(Membership.amount_paid).label('revenue')
            )
            .group_by(Membership.validity_days, Membership.tier)
            .order_by(func.count(Membership.id).desc())
        )
        
        plans = plan_stats.all()
        
        # Map days to display names
        validity_map = {
            30: "1 Month",
            90: "3 Months",
            120: "4 Months",
            180: "6 Months",
            365: "1 Year",
            730: "Lifetime"
        }
        
        text = "🎯 <b>Popular Plans</b>\n\n"
        
        if not plans:
            text += "No subscription data yet."
        else:
            total_subs = sum(p.count for p in plans)
            total_revenue = sum(p.revenue for p in plans)
            
            text += "<b>📊 Top Plans:</b>\n"
            for i, plan in enumerate(plans[:10], 1):
                plan_name = validity_map.get(plan.validity_days, f"{plan.validity_days} days")
                percentage = (plan.count / total_subs * 100) if total_subs > 0 else 0
                bar = "█" * int(percentage / 5)
                
                text += (
                    f"{i}. {plan_name} (Tier {plan.tier})\n"
                    f"   ├ Purchases: {plan.count} ({percentage:.1f}%)\n"
                    f"   └ Revenue: ₹{plan.revenue:.2f}\n"
                    f"   {bar}\n\n"
                )
            
            # Calculate average
            avg_amount = total_revenue / total_subs if total_subs > 0 else 0
            
            text += (
                f"<b>💰 Summary:</b>\n"
                f"├ Total Subscriptions: {total_subs}\n"
                f"├ Total Revenue: ₹{total_revenue:.2f}\n"
                f"└ Avg per Sub: ₹{avg_amount:.2f}\n"
            )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Refresh", callback_data="analytics_plans")],
            [InlineKeyboardButton(text="🔙 Back", callback_data="analytics_back")]
        ])
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    
    await callback.answer()


# =====================================================
# CONVERSION RATES
# =====================================================

@router.callback_query(F.data == "analytics_conversion")
async def analytics_conversion(callback: CallbackQuery):
    """Show conversion rates and funnel"""
    async with async_session() as session:
        # Total users (top of funnel)
        total_users = await session.execute(select(func.count(User.id)))
        total_users = total_users.scalar()
        
        # Users who made at least one payment
        paid_users = await session.execute(
            select(func.count(User.id.distinct()))
            .select_from(User)
            .join(Payment)
            .where(Payment.status == "captured")
        )
        paid_users = paid_users.scalar()
        
        # Users with active subscriptions
        active_users = await session.execute(
            select(func.count(User.id.distinct()))
            .select_from(User)
            .join(Membership)
            .where(Membership.is_active == True)
        )
        active_users = active_users.scalar()
        
        # Users who renewed (made 2+ payments)
        renewed_users = await session.execute(
            select(func.count(User.id.distinct()))
            .select_from(User)
            .join(Payment)
            .where(Payment.status == "captured")
            .group_by(User.id)
            .having(func.count(Payment.id) >= 2)
        )
        renewed_users = len(renewed_users.all())
        
        # Calculate conversion rates
        signup_to_paid = (paid_users / total_users * 100) if total_users > 0 else 0
        paid_to_active = (active_users / paid_users * 100) if paid_users > 0 else 0
        active_to_renewed = (renewed_users / active_users * 100) if active_users > 0 else 0
        
        # Churn rate (users who had subscription but now don't)
        churned_users = await session.execute(
            select(func.count(User.id.distinct()))
            .select_from(User)
            .join(Membership)
            .where(Membership.is_active == False)
        )
        churned_users = churned_users.scalar()
        
        ever_subscribed = paid_users
        churn_rate = (churned_users / ever_subscribed * 100) if ever_subscribed > 0 else 0
        retention_rate = 100 - churn_rate
        
        text = (
            f"📊 <b>Conversion Funnel</b>\n\n"
            f"<b>🔽 Customer Journey:</b>\n\n"
            f"1️⃣ Total Users: {total_users}\n"
            f"   ↓ {signup_to_paid:.1f}% converted\n\n"
            f"2️⃣ Paid Users: {paid_users}\n"
            f"   ↓ {paid_to_active:.1f}% active\n\n"
            f"3️⃣ Active Subscribers: {active_users}\n"
            f"   ↓ {active_to_renewed:.1f}% renewed\n\n"
            f"4️⃣ Repeat Customers: {renewed_users}\n\n"
            f"<b>📈 Key Metrics:</b>\n"
            f"├ Conversion Rate: {signup_to_paid:.1f}%\n"
            f"├ Retention Rate: {retention_rate:.1f}%\n"
            f"├ Churn Rate: {churn_rate:.1f}%\n"
            f"└ Renewal Rate: {active_to_renewed:.1f}%\n"
        )
        
        # Benchmarks
        text += "\n<b>💡 Benchmarks:</b>\n"
        
        if signup_to_paid < 5:
            text += "⚠️ Low conversion - improve onboarding\n"
        elif signup_to_paid > 20:
            text += "✅ Excellent conversion rate!\n"
        else:
            text += "📊 Average conversion rate\n"
        
        if churn_rate > 30:
            text += "⚠️ High churn - focus on retention\n"
        elif churn_rate < 10:
            text += "✅ Great retention!\n"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Refresh", callback_data="analytics_conversion")],
            [InlineKeyboardButton(text="🔙 Back", callback_data="analytics_back")]
        ])
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    
    await callback.answer()


# =====================================================
# BACK TO MAIN MENU
# =====================================================

@router.callback_query(F.data == "analytics_back")
async def analytics_back(callback: CallbackQuery):
    """Return to analytics main menu"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📈 Overview", callback_data="analytics_overview")],
        [InlineKeyboardButton(text="💰 Revenue Reports", callback_data="analytics_revenue")],
        [InlineKeyboardButton(text="📺 Channel Performance", callback_data="analytics_channels")],
        [InlineKeyboardButton(text="👥 User Growth", callback_data="analytics_users")],
        [InlineKeyboardButton(text="🎯 Popular Plans", callback_data="analytics_plans")],
        [InlineKeyboardButton(text="📊 Conversion Rates", callback_data="analytics_conversion")]
    ])
    
    await callback.message.edit_text(
        "📊 <b>Analytics Dashboard</b>\n\n"
        "Select a report to view:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback.answer()