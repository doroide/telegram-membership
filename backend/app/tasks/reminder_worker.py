from datetime import datetime, timezone, timedelta
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from backend.app.db.session import async_session
from backend.app.db.models import Membership
from backend.bot.bot import bot


async def run_reminder_check():
    """
    Send reminders to users whose membership is expiring soon
    Sends at:
    - 7 days before expiry
    - 1 day before expiry
    - On expiry day (before expiry_checker runs)
    - 4 hours after expiry
    """
    print("🔔 Running reminder check...")
    
    async with async_session() as session:
        # Load active + recently expired memberships
        result = await session.execute(
            select(Membership)
            .options(selectinload(Membership.user))
            .options(selectinload(Membership.channel))
        )
        memberships = result.scalars().all()
        
        now = datetime.now(timezone.utc)
        reminder_count = 0
        
        for m in memberships:
            if not m.expiry_date:
                continue
            
            expiry_tz = m.expiry_date
            if expiry_tz.tzinfo is None:
                expiry_tz = expiry_tz.replace(tzinfo=timezone.utc)
            
            time_diff = expiry_tz - now
            days_left = time_diff.days
            hours_left = time_diff.total_seconds() / 3600

            # Renew button
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

            # ==========================================
            # 7 DAYS BEFORE EXPIRY
            # ==========================================
            if days_left == 7 and m.is_active and not m.reminded_7d:
                try:
                    await bot.send_message(
                        chat_id=m.user.telegram_id,
                        text=(
                            f"⏰ <b>Reminder: Your Membership Expires Soon</b>\n\n"
                            f"📺 Channel: <b>{m.channel.name}</b>\n"
                            f"📅 Expires on: <b>{expiry_tz.strftime('%d %b %Y')}</b>\n"
                            f"⏳ Time left: <b>7 days</b>\n\n"
                            f"💡 Renew now to keep enjoying uninterrupted access.\n\n"
                            f"Tap below to renew 👇"
                        ),
                        reply_markup=keyboard,
                        parse_mode="HTML"
                    )
                    m.reminded_7d = True
                    reminder_count += 1
                    print(f"✅ 7-day reminder sent to user {m.user.telegram_id} for {m.channel.name}")
                except Exception as e:
                    print(f"⚠️ Failed to send 7-day reminder to {m.user.telegram_id}: {e}")

            # ==========================================
            # 1 DAY BEFORE EXPIRY
            # ==========================================
            elif days_left == 1 and m.is_active and not m.reminded_1d:
                try:
                    await bot.send_message(
                        chat_id=m.user.telegram_id,
                        text=(
                            f"⏰ <b>Reminder: Your Membership Expires Soon</b>\n\n"
                            f"📺 Channel: <b>{m.channel.name}</b>\n"
                            f"📅 Expires on: <b>{expiry_tz.strftime('%d %b %Y')}</b>\n"
                            f"⏳ Time left: <b>Less than 24 hours</b>\n\n"
                            f"💡 Renew now to keep enjoying uninterrupted access.\n\n"
                            f"Tap below to renew 👇"
                        ),
                        reply_markup=keyboard,
                        parse_mode="HTML"
                    )
                    m.reminded_1d = True
                    reminder_count += 1
                    print(f"✅ 1-day reminder sent to user {m.user.telegram_id} for {m.channel.name}")
                except Exception as e:
                    print(f"⚠️ Failed to send 1-day reminder to {m.user.telegram_id}: {e}")

            # ==========================================
            # ON EXPIRY DAY (before it expires)
            # ==========================================
            elif days_left == 0 and hours_left > 0 and m.is_active and not m.reminded_expired:
                try:
                    hours_remaining = int(hours_left)
                    await bot.send_message(
                        chat_id=m.user.telegram_id,
                        text=(
                            f"🔴 <b>Final Reminder: Membership Expires Today</b>\n\n"
                            f"📺 Channel: <b>{m.channel.name}</b>\n"
                            f"📅 Expires today at: <b>{expiry_tz.strftime('%I:%M %p')}</b>\n"
                            f"⏳ Time left: <b>~{hours_remaining} hours</b>\n\n"
                            f"⚡ Renew now to keep your access active."
                        ),
                        reply_markup=keyboard,
                        parse_mode="HTML"
                    )
                    m.reminded_expired = True
                    reminder_count += 1
                    print(f"✅ Expiry-day reminder sent to user {m.user.telegram_id} for {m.channel.name}")
                except Exception as e:
                    print(f"⚠️ Failed to send expiry-day reminder to {m.user.telegram_id}: {e}")

            # ==========================================
            # 4 HOURS AFTER EXPIRY
            # ==========================================
            elif not m.is_active and hours_left <= -4 and hours_left >= -5:
                try:
                    await bot.send_message(
                        chat_id=m.user.telegram_id,
                        text=(
                            f"⌛ <b>Your Membership Has Expired</b>\n\n"
                            f"📺 Channel: <b>{m.channel.name}</b>\n"
                            f"Access to this channel has ended.\n\n"
                            f"🔄 Renew now to regain access instantly."
                        ),
                        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(
                                text="🔄 Renew Now",
                                callback_data=f"userch_{m.channel_id}"
                            )]
                        ]),
                        parse_mode="HTML"
                    )
                    reminder_count += 1
                    print(f"✅ Post-expiry reminder sent to user {m.user.telegram_id} for {m.channel.name}")
                except Exception as e:
                    print(f"⚠️ Failed to send post-expiry reminder to {m.user.telegram_id}: {e}")

        await session.commit()
        
        if reminder_count > 0:
            print(f"✅ Sent {reminder_count} reminder(s)")
        else:
            print("✅ No reminders to send at this time")


async def scheduled_reminder_task():
    import asyncio
    while True:
        try:
            await run_reminder_check()
        except Exception as e:
            print(f"❌ Reminder task error: {e}")
        await asyncio.sleep(3600)  # Run every 1 hour