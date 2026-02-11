from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from backend.app.db.session import async_session
from backend.app.db.models import Membership
from backend.bot.bot import bot


async def run_expiry_check():
    """
    Check for expired memberships and remove users from channels
    Also resets reminder flags for renewed memberships
    """
    print("🔍 Running expiry check...")
    
    async with async_session() as session:
        # Load active memberships with related user and channel data
        result = await session.execute(
            select(Membership)
            .where(Membership.is_active == True)
            .options(selectinload(Membership.user))
            .options(selectinload(Membership.channel))
        )
        memberships = result.scalars().all()
        
        now = datetime.now(timezone.utc)
        expired_count = 0
        
        for m in memberships:
            if not m.expiry_date:
                continue
            
            # Make timezone-aware if needed
            expiry_tz = m.expiry_date
            if expiry_tz.tzinfo is None:
                expiry_tz = expiry_tz.replace(tzinfo=timezone.utc)
            
            if expiry_tz < now:
                # Mark as inactive
                m.is_active = False
                expired_count += 1
                
                try:
                    # Remove user from Telegram channel
                    await bot.ban_chat_member(
                        chat_id=m.channel.telegram_chat_id,
                        user_id=m.user.telegram_id
                    )
                    
                    # Immediately unban so they can rejoin if they renew
                    await bot.unban_chat_member(
                        chat_id=m.channel.telegram_chat_id,
                        user_id=m.user.telegram_id
                    )
                    
                    print(f"✅ Removed user {m.user.telegram_id} from channel {m.channel.name}")
                    
                    # Create renewal button
                    keyboard = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(
                            text="🔄 Renew Now",
                            callback_data=f"userch_{m.channel_id}"
                        )],
                        [InlineKeyboardButton(
                            text="📋 My Plans",
                            callback_data="my_plans"
                        )]
                    ])
                    
                    # Notify user
                    await bot.send_message(
                        chat_id=m.user.telegram_id,
                        text=(
                            f"❌ <b>Membership Expired</b>\n\n"
                            f"Your access to <b>{m.channel.name}</b> has ended.\n\n"
                            f"📅 Expired on: {expiry_tz.strftime('%d %b %Y')}\n\n"
                            f"💡 Click below to renew and regain access!"
                        ),
                        reply_markup=keyboard,
                        parse_mode="HTML"
                    )
                    
                except Exception as e:
                    print(f"⚠️ Failed to process expiry for user {m.user.telegram_id}: {e}")
        
        # Commit all changes
        await session.commit()
        
        if expired_count > 0:
            print(f"✅ Processed {expired_count} expired membership(s)")
        else:
            print("✅ No expired memberships found")