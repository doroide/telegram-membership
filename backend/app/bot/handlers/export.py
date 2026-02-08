import os
import csv
import io
from datetime import datetime, timedelta
from sqlalchemy import select, and_
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from backend.app.db.session import async_session
from backend.app.db.models import User, Channel, Membership, Payment

router = Router()

ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x]


# =====================================================
# FSM STATES FOR DATE FILTERING
# =====================================================
class ExportStates(StatesGroup):
    waiting_for_date_range = State()
    export_type = State()


# =====================================================
# HELPER: Generate CSV from data
# =====================================================
def generate_csv(headers, rows):
    """Generate CSV file content from headers and rows"""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    writer.writerows(rows)
    return output.getvalue()


# =====================================================
# EXPORT FUNCTIONS
# =====================================================

async def export_all_payments(start_date=None, end_date=None):
    """Export all payment records"""
    async with async_session() as session:
        # Build query
        query = (
            select(Payment, User, Channel)
            .join(User, Payment.user_id == User.id)
            .join(Channel, Payment.channel_id == Channel.id)
            .order_by(Payment.created_at.desc())
        )
        
        if start_date:
            query = query.where(Payment.created_at >= start_date)
        if end_date:
            query = query.where(Payment.created_at <= end_date)
        
        result = await session.execute(query)
        data = result.all()
        
        # Prepare CSV data
        headers = [
            "Payment ID",
            "Date",
            "User ID",
            "Username",
            "Channel",
            "Amount (₹)",
            "Status",
            "Payment Method"
        ]
        
        rows = []
        for payment, user, channel in data:
            rows.append([
                payment.payment_id,
                payment.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                user.telegram_id,
                user.username or "N/A",
                channel.name,
                f"{payment.amount:.2f}",
                payment.status,
                payment.payment_method or "N/A"
            ])
        
        return generate_csv(headers, rows), len(rows)


async def export_users_memberships():
    """Export all users with their membership details"""
    async with async_session() as session:
        # Get all users with their memberships
        query = (
            select(User, Membership, Channel)
            .outerjoin(Membership, User.id == Membership.user_id)
            .outerjoin(Channel, Membership.channel_id == Channel.id)
            .order_by(User.created_at.desc())
        )
        
        result = await session.execute(query)
        data = result.all()
        
        headers = [
            "User ID",
            "Username",
            "First Name",
            "Last Name",
            "Registered On",
            "Channel",
            "Plan Start",
            "Plan Expiry",
            "Status",
            "Amount Paid (₹)"
        ]
        
        rows = []
        for user, membership, channel in data:
            if membership:
                status = "Active" if membership.is_active and membership.expiry_date > datetime.utcnow() else "Expired"
                rows.append([
                    user.telegram_id,
                    user.username or "N/A",
                    user.first_name or "N/A",
                    user.last_name or "N/A",
                    user.created_at.strftime("%Y-%m-%d %H:%M:%S") if user.created_at else "N/A",
                    channel.name if channel else "N/A",
                    membership.start_date.strftime("%Y-%m-%d") if membership.start_date else "N/A",
                    membership.expiry_date.strftime("%Y-%m-%d") if membership.expiry_date else "N/A",
                    status,
                    f"{membership.amount_paid:.2f}" if membership.amount_paid else "0.00"
                ])
            else:
                # User with no memberships
                rows.append([
                    user.telegram_id,
                    user.username or "N/A",
                    user.first_name or "N/A",
                    user.last_name or "N/A",
                    user.created_at.strftime("%Y-%m-%d %H:%M:%S") if user.created_at else "N/A",
                    "No Membership",
                    "N/A",
                    "N/A",
                    "N/A",
                    "0.00"
                ])
        
        return generate_csv(headers, rows), len(rows)


async def export_channel_performance():
    """Export channel-wise performance metrics"""
    async with async_session() as session:
        # Get all channels
        channels_result = await session.execute(select(Channel))
        channels = channels_result.scalars().all()
        
        headers = [
            "Channel ID",
            "Channel Name",
            "Plan Type",
            "Total Revenue (₹)",
            "Total Payments",
            "Active Members",
            "Expired Members",
            "Total Members",
            "Created On"
        ]
        
        rows = []
        now = datetime.utcnow()
        
        for channel in channels:
            # Get revenue
            revenue_query = select(Payment).where(
                Payment.channel_id == channel.id,
                Payment.status == "captured"
            )
            revenue_result = await session.execute(revenue_query)
            payments = revenue_result.scalars().all()
            
            total_revenue = sum(p.amount for p in payments)
            payment_count = len(payments)
            
            # Get memberships
            membership_query = select(Membership).where(
                Membership.channel_id == channel.id
            )
            membership_result = await session.execute(membership_query)
            memberships = membership_result.scalars().all()
            
            active_count = sum(1 for m in memberships if m.is_active and m.expiry_date > now)
            expired_count = sum(1 for m in memberships if not m.is_active or m.expiry_date <= now)
            total_members = len(memberships)
            
            rows.append([
                channel.telegram_chat_id,
                channel.name,
                channel.plan_slab or "N/A",
                f"{total_revenue:.2f}",
                payment_count,
                active_count,
                expired_count,
                total_members,
                channel.created_at.strftime("%Y-%m-%d") if channel.created_at else "N/A"
            ])
        
        return generate_csv(headers, rows), len(rows)


async def export_active_members():
    """Export only currently active members"""
    async with async_session() as session:
        now = datetime.utcnow()
        
        query = (
            select(User, Membership, Channel)
            .join(Membership, User.id == Membership.user_id)
            .join(Channel, Membership.channel_id == Channel.id)
            .where(
                Membership.is_active == True,
                Membership.expiry_date > now
            )
            .order_by(Membership.expiry_date.asc())
        )
        
        result = await session.execute(query)
        data = result.all()
        
        headers = [
            "User ID",
            "Username",
            "First Name",
            "Channel",
            "Started On",
            "Expires On",
            "Days Remaining",
            "Amount Paid (₹)"
        ]
        
        rows = []
        for user, membership, channel in data:
            days_remaining = (membership.expiry_date - now).days
            rows.append([
                user.telegram_id,
                user.username or "N/A",
                user.first_name or "N/A",
                channel.name,
                membership.start_date.strftime("%Y-%m-%d"),
                membership.expiry_date.strftime("%Y-%m-%d"),
                days_remaining,
                f"{membership.amount_paid:.2f}"
            ])
        
        return generate_csv(headers, rows), len(rows)


async def export_expired_members():
    """Export expired members for remarketing"""
    async with async_session() as session:
        now = datetime.utcnow()
        
        query = (
            select(User, Membership, Channel)
            .join(Membership, User.id == Membership.user_id)
            .join(Channel, Membership.channel_id == Channel.id)
            .where(
                and_(
                    Membership.expiry_date <= now,
                    Membership.is_active == False
                )
            )
            .order_by(Membership.expiry_date.desc())
        )
        
        result = await session.execute(query)
        data = result.all()
        
        headers = [
            "User ID",
            "Username",
            "First Name",
            "Channel",
            "Expired On",
            "Days Since Expiry",
            "Last Amount Paid (₹)"
        ]
        
        rows = []
        for user, membership, channel in data:
            days_expired = (now - membership.expiry_date).days
            rows.append([
                user.telegram_id,
                user.username or "N/A",
                user.first_name or "N/A",
                channel.name,
                membership.expiry_date.strftime("%Y-%m-%d"),
                days_expired,
                f"{membership.amount_paid:.2f}"
            ])
        
        return generate_csv(headers, rows), len(rows)


# =====================================================
# EXPORT COMMAND HANDLERS
# =====================================================

@router.message(Command("export"))
async def export_command(message: Message):
    """Main export command - shows export options"""
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔ This command is for admins only.")
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💳 All Payments", callback_data="export_payments"),
        ],
        [
            InlineKeyboardButton(text="👥 Users & Memberships", callback_data="export_users"),
        ],
        [
            InlineKeyboardButton(text="📺 Channel Performance", callback_data="export_channels"),
        ],
        [
            InlineKeyboardButton(text="✅ Active Members", callback_data="export_active"),
        ],
        [
            InlineKeyboardButton(text="❌ Expired Members", callback_data="export_expired"),
        ],
        [
            InlineKeyboardButton(text="📅 Payments (Date Filter)", callback_data="export_payments_filtered"),
        ]
    ])
    
    await message.answer(
        "📤 <b>Data Export</b>\n\n"
        "Select the type of data you want to export as CSV:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


@router.callback_query(F.data == "export_payments")
async def export_payments_callback(callback: CallbackQuery):
    """Export all payments"""
    await callback.message.edit_text("⏳ Generating payments export...")
    
    try:
        csv_content, row_count = await export_all_payments()
        
        # Create file
        filename = f"payments_export_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
        file = BufferedInputFile(csv_content.encode('utf-8'), filename=filename)
        
        await callback.message.answer_document(
            document=file,
            caption=f"✅ <b>Payments Export Complete</b>\n\n📊 Total Records: {row_count}",
            parse_mode="HTML"
        )
        
        await callback.message.delete()
        
    except Exception as e:
        await callback.message.edit_text(f"❌ Export failed: {str(e)}")
    
    await callback.answer()


@router.callback_query(F.data == "export_users")
async def export_users_callback(callback: CallbackQuery):
    """Export users and memberships"""
    await callback.message.edit_text("⏳ Generating users & memberships export...")
    
    try:
        csv_content, row_count = await export_users_memberships()
        
        filename = f"users_memberships_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
        file = BufferedInputFile(csv_content.encode('utf-8'), filename=filename)
        
        await callback.message.answer_document(
            document=file,
            caption=f"✅ <b>Users & Memberships Export Complete</b>\n\n📊 Total Records: {row_count}",
            parse_mode="HTML"
        )
        
        await callback.message.delete()
        
    except Exception as e:
        await callback.message.edit_text(f"❌ Export failed: {str(e)}")
    
    await callback.answer()


@router.callback_query(F.data == "export_channels")
async def export_channels_callback(callback: CallbackQuery):
    """Export channel performance"""
    await callback.message.edit_text("⏳ Generating channel performance export...")
    
    try:
        csv_content, row_count = await export_channel_performance()
        
        filename = f"channel_performance_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
        file = BufferedInputFile(csv_content.encode('utf-8'), filename=filename)
        
        await callback.message.answer_document(
            document=file,
            caption=f"✅ <b>Channel Performance Export Complete</b>\n\n📊 Total Channels: {row_count}",
            parse_mode="HTML"
        )
        
        await callback.message.delete()
        
    except Exception as e:
        await callback.message.edit_text(f"❌ Export failed: {str(e)}")
    
    await callback.answer()


@router.callback_query(F.data == "export_active")
async def export_active_callback(callback: CallbackQuery):
    """Export active members"""
    await callback.message.edit_text("⏳ Generating active members export...")
    
    try:
        csv_content, row_count = await export_active_members()
        
        filename = f"active_members_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
        file = BufferedInputFile(csv_content.encode('utf-8'), filename=filename)
        
        await callback.message.answer_document(
            document=file,
            caption=f"✅ <b>Active Members Export Complete</b>\n\n📊 Total Active: {row_count}",
            parse_mode="HTML"
        )
        
        await callback.message.delete()
        
    except Exception as e:
        await callback.message.edit_text(f"❌ Export failed: {str(e)}")
    
    await callback.answer()


@router.callback_query(F.data == "export_expired")
async def export_expired_callback(callback: CallbackQuery):
    """Export expired members"""
    await callback.message.edit_text("⏳ Generating expired members export...")
    
    try:
        csv_content, row_count = await export_expired_members()
        
        filename = f"expired_members_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
        file = BufferedInputFile(csv_content.encode('utf-8'), filename=filename)
        
        await callback.message.answer_document(
            document=file,
            caption=f"✅ <b>Expired Members Export Complete</b>\n\n📊 Total Expired: {row_count}",
            parse_mode="HTML"
        )
        
        await callback.message.delete()
        
    except Exception as e:
        await callback.message.edit_text(f"❌ Export failed: {str(e)}")
    
    await callback.answer()


@router.callback_query(F.data == "export_payments_filtered")
async def export_payments_filtered_callback(callback: CallbackQuery, state: FSMContext):
    """Show date range options for payment export"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📅 Last 7 Days", callback_data="filter_7days"),
        ],
        [
            InlineKeyboardButton(text="📅 Last 30 Days", callback_data="filter_30days"),
        ],
        [
            InlineKeyboardButton(text="📅 This Month", callback_data="filter_thismonth"),
        ],
        [
            InlineKeyboardButton(text="📅 Last Month", callback_data="filter_lastmonth"),
        ],
        [
            InlineKeyboardButton(text="🔙 Back", callback_data="export_back"),
        ]
    ])
    
    await callback.message.edit_text(
        "📅 <b>Select Date Range</b>\n\n"
        "Choose a time period for payment export:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("filter_"))
async def export_filtered_payments(callback: CallbackQuery):
    """Export payments with date filter"""
    filter_type = callback.data.split("_")[1]
    
    now = datetime.utcnow()
    start_date = None
    end_date = now
    period_name = ""
    
    if filter_type == "7days":
        start_date = now - timedelta(days=7)
        period_name = "Last 7 Days"
    elif filter_type == "30days":
        start_date = now - timedelta(days=30)
        period_name = "Last 30 Days"
    elif filter_type == "thismonth":
        start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        period_name = "This Month"
    elif filter_type == "lastmonth":
        # Calculate last month
        first_this_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end_date = first_this_month - timedelta(days=1)
        start_date = end_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        period_name = "Last Month"
    
    await callback.message.edit_text(f"⏳ Generating export for {period_name}...")
    
    try:
        csv_content, row_count = await export_all_payments(start_date, end_date)
        
        filename = f"payments_{filter_type}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
        file = BufferedInputFile(csv_content.encode('utf-8'), filename=filename)
        
        await callback.message.answer_document(
            document=file,
            caption=(
                f"✅ <b>Payments Export Complete</b>\n\n"
                f"📅 Period: {period_name}\n"
                f"📊 Total Records: {row_count}"
            ),
            parse_mode="HTML"
        )
        
        await callback.message.delete()
        
    except Exception as e:
        await callback.message.edit_text(f"❌ Export failed: {str(e)}")
    
    await callback.answer()


@router.callback_query(F.data == "export_back")
async def export_back_callback(callback: CallbackQuery):
    """Return to main export menu"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💳 All Payments", callback_data="export_payments"),
        ],
        [
            InlineKeyboardButton(text="👥 Users & Memberships", callback_data="export_users"),
        ],
        [
            InlineKeyboardButton(text="📺 Channel Performance", callback_data="export_channels"),
        ],
        [
            InlineKeyboardButton(text="✅ Active Members", callback_data="export_active"),
        ],
        [
            InlineKeyboardButton(text="❌ Expired Members", callback_data="export_expired"),
        ],
        [
            InlineKeyboardButton(text="📅 Payments (Date Filter)", callback_data="export_payments_filtered"),
        ]
    ])
    
    await callback.message.edit_text(
        "📤 <b>Data Export</b>\n\n"
        "Select the type of data you want to export as CSV:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback.answer()