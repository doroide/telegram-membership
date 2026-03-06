from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from backend.app.tasks.expiry_checker import run_expiry_check
from backend.app.tasks.reminder_worker import run_reminder_check
from backend.app.tasks.reports import (
    send_daily_report,
    send_weekly_report,
    send_monthly_report,
    send_yearly_report,
)

scheduler = AsyncIOScheduler()


def start_scheduler():
    # Expiry check – every hour
    scheduler.add_job(
        run_expiry_check,
        CronTrigger(minute=0),
        id="expiry_check",
        replace_existing=True
    )

    # Reminder worker – 9 AM & 6 PM UTC
    scheduler.add_job(
        run_reminder_check,
        CronTrigger(hour="9,18", minute=0),
        id="reminder_check",
        replace_existing=True
    )

    # Daily report – 9 AM IST
    scheduler.add_job(
        send_daily_report,
        CronTrigger(hour=3, minute=30),
        id="daily_report",
        replace_existing=True
    )

    # Weekly report – Monday 9 AM IST
    scheduler.add_job(
        send_weekly_report,
        CronTrigger(day_of_week="mon", hour=3, minute=30),
        id="weekly_report",
        replace_existing=True
    )

    # Monthly report – 1st day 9 AM IST
    scheduler.add_job(
        send_monthly_report,
        CronTrigger(day=1, hour=3, minute=30),
        id="monthly_report",
        replace_existing=True
    )

    # Yearly report – Jan 1st 9 AM IST
    scheduler.add_job(
        send_yearly_report,
        CronTrigger(month=1, day=1, hour=3, minute=30),
        id="yearly_report",
        replace_existing=True
    )

    scheduler.start()
    print("✅ Scheduler started (daily / weekly / monthly / yearly reports enabled)")


def stop_scheduler():
    scheduler.shutdown()
    print("🛑 Scheduler stopped")
