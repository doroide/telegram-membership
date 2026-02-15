import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from backend.app.tasks.expiry_checker import run_expiry_check
from backend.app.tasks.reminder_worker import run_reminder_check
from backend.app.tasks.reports import send_daily_report, send_weekly_report


scheduler = AsyncIOScheduler()


def start_scheduler():
    """
    Start background tasks scheduler
    """
    # Run expiry check every hour
    scheduler.add_job(
        run_expiry_check,
        trigger=CronTrigger(minute=0),  # Every hour at :00
        id="expiry_check",
        name="Check expired memberships",
        replace_existing=True
    )
    
    # Run reminder check twice daily (9 AM and 6 PM UTC)
    scheduler.add_job(
        run_reminder_check,
        trigger=CronTrigger(hour="9,18", minute=0),
        id="reminder_check",
        name="Send membership reminders",
        replace_existing=True
    )

        # 📊 Daily report – 9 AM IST (03:30 UTC)
    scheduler.add_job(
        send_daily_report,
        CronTrigger(hour=3, minute=30),
        id="daily_report",
        replace_existing=True
    )

    # 📊 Weekly report – Monday 9 AM IST
    scheduler.add_job(
        send_weekly_report,
        CronTrigger(day_of_week="mon", hour=3, minute=30),
        id="weekly_report",
        replace_existing=True
    )

    
    scheduler.start()
    print("✅ Scheduler started:")
    print("   - Expiry check: Every hour")
    print("   - Reminders: Daily at 9 AM & 6 PM UTC")


def stop_scheduler():
    """
    Stop the scheduler gracefully
    """
    scheduler.shutdown()
    print("🛑 Scheduler stopped")