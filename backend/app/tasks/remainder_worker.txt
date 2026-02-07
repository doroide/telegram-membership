from datetime import datetime, timezone, timedelta
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from backend.app.db.session import async_session
from backend.app.db.models import Membership
from backend.bot.bot import bot


async def run_reminder_check():
    """
    Send reminders to users whose membership is expiring soon
    Sends at 3 days and 1 day before expiry
    """
    print("🔔 Running reminder check...")
    
    async with async_session() as session:
        # Load active memberships with user and channel data
        result = await session.execute(
            select(Membership)
            .where(Membership.is_active == True)
            .options(selectinload(Membership.user))
            .options(selectinload(Membership.channel))
        )
        memberships = result.scalars().all()
        
        now = datetime.now(timezone.utc)
        reminder_count = 0
        
        for m in memberships:
            if not m.expiry_date:
                continue
            
            expiry_tz = m.expiry_date.replace(tzinfo=timezone.utc)
            days_left = (expiry_tz - now).days
            
            # Send reminder at 3 days or 1 day before expiry
            if days_left in [3, 1]:
                try:
                    await bot.send_message(
                        chat_id=m.user.telegram_id,
                        text=(
                            f"⏰ <b>Membership Expiring Soon!</b>\n\n"
                            f"📺 Channel: <b>{m.channel.name}</b>\n"
                            f"⏳ Days left: <b>{days_left}</b>\n"
                            f"📅 Expires: <b>{expiry_tz.strftime('%d %b %Y')}</b>\n\n"
                            f"💡 Use /renew to extend your membership and keep access!"
                        ),
                        parse_mode="HTML"
                    )
                    
                    reminder_count += 1
                    print(f"✅ Sent reminder to user {m.user.telegram_id} ({days_left} days left)")
                    
                except Exception as e:
                    print(f"⚠️ Failed to send reminder to {m.user.telegram_id}: {e}")
        
        if reminder_count > 0:
            print(f"✅ Sent {reminder_count} reminders")
        else:
            print("✅ No reminders to send")