from datetime import datetime, timezone, timedelta
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select, func

from backend.app.db.session import async_session
from backend.app.db.models import UpsellAttempt

router = Router()


# =====================================================
# UPSELL STATS - MAIN VIEW
# =====================================================

@router.callback_query(F.data == "upsell_stats")
async def upsell_stats(callback: CallbackQuery):
    """Show upsell performance stats"""
    
    async with async_session() as session:
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        # Today's stats
        today_result = await session.execute(
            select(
                func.count(UpsellAttempt.id).label('total'),
                func.count(UpsellAttempt.id).filter(UpsellAttempt.accepted == True).label('accepted'),
                func.sum(UpsellAttempt.discount_amount).filter(UpsellAttempt.accepted == True).label('revenue')
            )
            .where(UpsellAttempt.created_at >= today_start)
        )
        today = today_result.first()
        
        # This month's stats
        month_result = await session.execute(
            select(
                func.count(UpsellAttempt.id).label('total'),
                func.count(UpsellAttempt.id).filter(UpsellAttempt.accepted == True).label('accepted'),
                func.sum(UpsellAttempt.discount_amount).filter(UpsellAttempt.accepted == True).label('revenue')
            )
            .where(UpsellAttempt.created_at >= month_start)
        )
        month = month_result.first()
        
        # Best performing upsell paths
        best_result = await session.execute(
            select(
                UpsellAttempt.from_validity_days,
                UpsellAttempt.to_validity_days,
                func.count(UpsellAttempt.id).label('total'),
                func.count(UpsellAttempt.id).filter(UpsellAttempt.accepted == True).label('accepted')
            )
            .where(UpsellAttempt.created_at >= month_start)
            .group_by(UpsellAttempt.from_validity_days, UpsellAttempt.to_validity_days)
            .order_by(func.count(UpsellAttempt.id).filter(UpsellAttempt.accepted == True).desc())
        )
        best_paths = best_result.all()
        
        # Calculate percentages
        today_conversion = (today.accepted / today.total * 100) if today.total > 0 else 0
        month_conversion = (month.accepted / month.total * 100) if month.total > 0 else 0
        
        # Format display names
        def format_plan(days):
            return {30: "1M", 90: "3M", 120: "4M", 180: "6M", 365: "1Y"}.get(days, f"{days}d")
        
        # Build best performers text
        best_text = ""
        for idx, (from_days, to_days, total, accepted) in enumerate(best_paths[:3], 1):
            conversion = (accepted / total * 100) if total > 0 else 0
            best_text += f"{idx}. {format_plan(from_days)} → {format_plan(to_days)}: {accepted}/{total} ({conversion:.1f}%)\n"
        
        if not best_text:
            best_text = "No data yet"
        
        response = (
            f"🎁 <b>Upselling Performance</b>\n\n"
            f"📅 <b>TODAY ({now.strftime('%d %b')})</b>\n"
            f"Offers shown: {today.total}\n"
            f"Accepted: {today.accepted} ({today_conversion:.1f}%)\n"
            f"Revenue: ₹{int(today.revenue or 0)}\n\n"
            f"📊 <b>THIS MONTH ({now.strftime('%b %Y')})</b>\n"
            f"Offers shown: {month.total}\n"
            f"Accepted: {month.accepted} ({month_conversion:.1f}%)\n"
            f"Revenue: ₹{int(month.revenue or 0)}\n\n"
            f"🏆 <b>BEST PERFORMERS</b>\n"
            f"{best_text}\n"
        )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📅 Daily Report", callback_data="upsell_daily")],
            [InlineKeyboardButton(text="📆 Monthly Report", callback_data="upsell_monthly")],
            [InlineKeyboardButton(text="📈 Conversion Trends", callback_data="upsell_trends")],
            [InlineKeyboardButton(text="🔙 Back to Admin", callback_data="admin_panel")]
        ])
        
        await callback.message.edit_text(response, reply_markup=keyboard, parse_mode="HTML")
        await callback.answer()


# =====================================================
# DAILY REPORT
# =====================================================

@router.callback_query(F.data == "upsell_daily")
async def upsell_daily(callback: CallbackQuery):
    """Show detailed daily upsell report"""
    
    async with async_session() as session:
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Get all upsell attempts today
        result = await session.execute(
            select(
                UpsellAttempt.from_validity_days,
                UpsellAttempt.to_validity_days,
                UpsellAttempt.from_amount,
                UpsellAttempt.to_amount,
                UpsellAttempt.discount_amount,
                UpsellAttempt.accepted
            )
            .where(UpsellAttempt.created_at >= today_start)
            .order_by(UpsellAttempt.created_at.desc())
        )
        attempts = result.all()
        
        if not attempts:
            response = f"📅 <b>Daily Report - {now.strftime('%d %b %Y')}</b>\n\nNo upsell attempts today."
        else:
            total = len(attempts)
            accepted = sum(1 for a in attempts if a.accepted)
            total_revenue = sum(a.to_amount for a in attempts if a.accepted)
            
            response = (
                f"📅 <b>Daily Report - {now.strftime('%d %b %Y')}</b>\n\n"
                f"📊 Summary:\n"
                f"Total offers: {total}\n"
                f"Accepted: {accepted} ({accepted/total*100:.1f}%)\n"
                f"Declined: {total - accepted}\n"
                f"Revenue: ₹{int(total_revenue)}\n\n"
            )
            
            # Group by upsell path
            from collections import defaultdict
            paths = defaultdict(lambda: {'total': 0, 'accepted': 0, 'revenue': 0})
            
            for attempt in attempts:
                key = (attempt.from_validity_days, attempt.to_validity_days)
                paths[key]['total'] += 1
                if attempt.accepted:
                    paths[key]['accepted'] += 1
                    paths[key]['revenue'] += attempt.to_amount
            
            response += "📈 By Upgrade Path:\n"
            for (from_days, to_days), stats in sorted(paths.items(), key=lambda x: x[1]['accepted'], reverse=True):
                from_name = {30: "1M", 90: "3M", 120: "4M", 180: "6M", 365: "1Y"}.get(from_days, f"{from_days}d")
                to_name = {30: "1M", 90: "3M", 120: "4M", 180: "6M", 365: "1Y"}.get(to_days, f"{to_days}d")
                conv = (stats['accepted'] / stats['total'] * 100) if stats['total'] > 0 else 0
                response += f"{from_name}→{to_name}: {stats['accepted']}/{stats['total']} ({conv:.0f}%) - ₹{int(stats['revenue'])}\n"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Back to Upsell Stats", callback_data="upsell_stats")]
        ])
        
        await callback.message.edit_text(response, reply_markup=keyboard, parse_mode="HTML")
        await callback.answer()


# =====================================================
# MONTHLY REPORT
# =====================================================

@router.callback_query(F.data == "upsell_monthly")
async def upsell_monthly(callback: CallbackQuery):
    """Show detailed monthly upsell report"""
    
    async with async_session() as session:
        now = datetime.now(timezone.utc)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        # Get all upsell attempts this month
        result = await session.execute(
            select(
                UpsellAttempt.from_validity_days,
                UpsellAttempt.to_validity_days,
                UpsellAttempt.from_amount,
                UpsellAttempt.to_amount,
                UpsellAttempt.discount_amount,
                UpsellAttempt.accepted
            )
            .where(UpsellAttempt.created_at >= month_start)
            .order_by(UpsellAttempt.created_at.desc())
        )
        attempts = result.all()
        
        if not attempts:
            response = f"📆 <b>Monthly Report - {now.strftime('%B %Y')}</b>\n\nNo upsell attempts this month."
        else:
            total = len(attempts)
            accepted = sum(1 for a in attempts if a.accepted)
            total_revenue = sum(a.to_amount for a in attempts if a.accepted)
            avg_upsell = total_revenue / accepted if accepted > 0 else 0
            
            response = (
                f"📆 <b>Monthly Report - {now.strftime('%B %Y')}</b>\n\n"
                f"💰 REVENUE\n"
                f"Total: ₹{int(total_revenue)}\n"
                f"Avg per upsell: ₹{int(avg_upsell)}\n\n"
                f"📊 CONVERSION\n"
                f"Offers shown: {total}\n"
                f"Accepted: {accepted} ({accepted/total*100:.1f}%)\n"
                f"Declined: {total - accepted} ({(total-accepted)/total*100:.1f}%)\n\n"
            )
            
            # Group by upsell path
            from collections import defaultdict
            paths = defaultdict(lambda: {'total': 0, 'accepted': 0, 'revenue': 0})
            
            for attempt in attempts:
                key = (attempt.from_validity_days, attempt.to_validity_days)
                paths[key]['total'] += 1
                if attempt.accepted:
                    paths[key]['accepted'] += 1
                    paths[key]['revenue'] += attempt.to_amount
            
            response += "🏆 TOP PERFORMERS:\n"
            sorted_paths = sorted(paths.items(), key=lambda x: x[1]['revenue'], reverse=True)
            for idx, ((from_days, to_days), stats) in enumerate(sorted_paths[:5], 1):
                from_name = {30: "1M", 90: "3M", 120: "4M", 180: "6M", 365: "1Y"}.get(from_days, f"{from_days}d")
                to_name = {30: "1M", 90: "3M", 120: "4M", 180: "6M", 365: "1Y"}.get(to_days, f"{to_days}d")
                conv = (stats['accepted'] / stats['total'] * 100) if stats['total'] > 0 else 0
                response += f"{idx}. {from_name}→{to_name}: ₹{int(stats['revenue'])} ({stats['accepted']}/{stats['total']}, {conv:.0f}%)\n"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Back to Upsell Stats", callback_data="upsell_stats")]
        ])
        
        await callback.message.edit_text(response, reply_markup=keyboard, parse_mode="HTML")
        await callback.answer()


# =====================================================
# CONVERSION TRENDS
# =====================================================

@router.callback_query(F.data == "upsell_trends")
async def upsell_trends(callback: CallbackQuery):
    """Show conversion trends over time"""
    
    async with async_session() as session:
        now = datetime.now(timezone.utc)
        
        # Last 7 days
        trends = []
        for i in range(6, -1, -1):
            day_start = (now - timedelta(days=i)).replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day_start + timedelta(days=1)
            
            result = await session.execute(
                select(
                    func.count(UpsellAttempt.id).label('total'),
                    func.count(UpsellAttempt.id).filter(UpsellAttempt.accepted == True).label('accepted')
                )
                .where(
                    UpsellAttempt.created_at >= day_start,
                    UpsellAttempt.created_at < day_end
                )
            )
            day_stats = result.first()
            
            conversion = (day_stats.accepted / day_stats.total * 100) if day_stats.total > 0 else 0
            trends.append({
                'date': day_start.strftime('%d %b'),
                'total': day_stats.total,
                'accepted': day_stats.accepted,
                'conversion': conversion
            })
        
        # Build response
        response = f"📈 <b>7-Day Conversion Trends</b>\n\n"
        
        for trend in trends:
            bar = "█" * int(trend['conversion'] / 10)  # Visual bar (max 10 blocks for 100%)
            response += (
                f"{trend['date']}: {trend['accepted']}/{trend['total']} "
                f"({trend['conversion']:.0f}%) {bar}\n"
            )
        
        # Calculate average
        avg_conversion = sum(t['conversion'] for t in trends) / 7
        response += f"\n📊 7-day avg: {avg_conversion:.1f}%"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Back to Upsell Stats", callback_data="upsell_stats")]
        ])
        
        await callback.message.edit_text(response, reply_markup=keyboard, parse_mode="HTML")
        await callback.answer()