import os
from datetime import datetime
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.app.db.session import async_session
from backend.app.db.models import User, Channel, Membership

router = Router()


# =====================================================
# /MYPLANS COMMAND
# =====================================================

@router.message(Command("myplans"))
async def myplans_command(message: Message):
    """Show user's all memberships (public + private channels)"""
    await show_user_plans(message.from_user.id, message=message)


@router.callback_query(F.data == "my_plans")
async def myplans_callback(callback: CallbackQuery):
    """Show user's all memberships via callback"""
    await show_user_plans(callback.from_user.id, callback=callback)


async def show_user_plans(telegram_id: int, message: Message = None, callback: CallbackQuery = None):
    """
    Display all user memberships
    Shows both public and private channel memberships
    """
    async with async_session() as session:
        # Get user
        user_result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = user_result.scalar_one_or_none()
        
        if not user:
            text = "❌ User not found. Please start with /start"
            if callback:
                await callback.answer(text, show_alert=True)
            else:
                await message.answer(text)
            return
        
        # Get all memberships (active and expired)
        memberships_result = await session.execute(
            select(Membership, Channel)
            .join(Channel, Membership.channel_id == Channel.id)
            .where(Membership.user_id == user.id)
            .order_by(Membership.is_active.desc(), Membership.expiry_date.desc())
        )
        memberships_data = memberships_result.all()
        
        if not memberships_data:
            text = (
                "📋 <b>My Plans</b>\n\n"
                "You don't have any subscriptions yet.\n\n"
                "Use /start to browse available channels!"
            )
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Back to Channels", callback_data="back_to_channels")]
            ])
            
            if callback:
                try:
                    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
                except Exception as e:
                    if "message is not modified" in str(e):
                        pass  # Message is already showing this
                    else:
                        raise e
                finally:
                    await callback.answer()
            else:
                await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
            return
        
        # Build response with tier info
        tier_display = f"Tier {user.current_tier}"
        if user.is_lifetime_member:
            tier_display = f"Lifetime Member (₹{user.lifetime_amount})"
        
        response = (
            f"📋 <b>My Subscriptions</b>\n\n"
            f"💎 Your Tier: {tier_display}\n\n"
        )
        
        now = datetime.utcnow()
        active_plans = []
        expired_plans = []
        
        # Separate active and expired
        for membership, channel in memberships_data:
            if membership.is_active and membership.expiry_date > now:
                active_plans.append((membership, channel))
            else:
                expired_plans.append((membership, channel))
        
        # Show active plans
        if active_plans:
            response += "✅ <b>Active Plans:</b>\n\n"
            for membership, channel in active_plans:
                days_left = (membership.expiry_date - now).days
                visibility = "🔓" if channel.is_public else "🔒"
                
                response += (
                    f"{visibility} <b>{channel.name}</b>\n"
                    f"   • Expires: {membership.expiry_date.strftime('%d %b %Y')}\n"
                    f"   • Days left: {days_left}\n"
                    f"   • Amount: ₹{membership.amount_paid}\n\n"
                )
        
        # Show expired plans
        if expired_plans:
            response += "⏰ <b>Expired Plans:</b>\n\n"
            for membership, channel in expired_plans:
                visibility = "🔓" if channel.is_public else "🔒"
                
                response += (
                    f"{visibility} <b>{channel.name}</b>\n"
                    f"   • Expired: {membership.expiry_date.strftime('%d %b %Y')}\n"
                    f"   • Amount: ₹{membership.amount_paid}\n\n"
                )
        
        # Build keyboard with renew options
        keyboard = []
        
        # Add renew buttons for expired plans
        if expired_plans:
            for membership, channel in expired_plans:
                keyboard.append([
                    InlineKeyboardButton(
                        text=f"🔄 Renew {channel.name}",
                        callback_data=f"userch_{channel.id}"
                    )
                ])
        
        # Add extend buttons for active plans
        if active_plans:
            keyboard.append([
                InlineKeyboardButton(
                    text="➕ Extend Active Plans",
                    callback_data="extend_info"
                )
            ])
        
        keyboard.append([
            InlineKeyboardButton(text="🔙 Back to Channels", callback_data="back_to_channels")
        ])
        
        if callback:
            try:
                await callback.message.edit_text(
                    response,
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
                    parse_mode="HTML"
                )
            except Exception as e:
                # If message content is the same, just answer the callback
                if "message is not modified" in str(e):
                    pass  # Will answer at the end
                else:
                    raise e
            finally:
                await callback.answer()
        else:
            await message.answer(
                response,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
                parse_mode="HTML"
            )


# =====================================================
# EXTEND INFO
# =====================================================

@router.callback_query(F.data == "extend_info")
async def extend_info_callback(callback: CallbackQuery):
    """Show info about extending active plans"""
    try:
        await callback.message.edit_text(
            "➕ <b>Extend Active Plans</b>\n\n"
            "To extend your active subscription:\n\n"
            "1. Go back to channels\n"
            "2. Select the channel you want to extend\n"
            "3. Purchase another plan\n\n"
            "⚠️ New validity will be added to your current expiry date!",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Back to My Plans", callback_data="my_plans")],
                [InlineKeyboardButton(text="📺 Browse Channels", callback_data="back_to_channels")]
            ]),
            parse_mode="HTML"
        )
    except Exception as e:
        if "message is not modified" not in str(e):
            raise e
    finally:
        await callback.answer()