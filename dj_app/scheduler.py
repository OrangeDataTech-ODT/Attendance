"""
Django APScheduler configuration — runs fetch_daily_punch_data 3 times per day (IST).
"""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from django_apscheduler.jobstores import DjangoJobStore, register_events
from django.core.management import call_command
import logging
import pytz

logger = logging.getLogger(__name__)


def fetch_daily_punch_data_job():
    """Fetch and save today's punch data (11:00 AM, 3:00 PM, 11:59 PM IST)."""
    try:
        logger.info("Starting scheduled fetch_daily_punch_data job")
        call_command('fetch_daily_punch_data', verbosity=1)
        logger.info("Completed scheduled fetch_daily_punch_data job")
    except Exception as e:
        logger.error(f"Error in scheduled fetch_daily_punch_data job: {str(e)}", exc_info=True)


_scheduler_instance = None
_scheduler_lock = False


def start_scheduler():
    """Start APScheduler with only the 3 daily punch-data fetch jobs."""
    global _scheduler_instance, _scheduler_lock

    if _scheduler_lock:
        logger.warning("Scheduler is already starting. Skipping duplicate start.")
        return

    if _scheduler_instance is not None and _scheduler_instance.running:
        logger.info("Scheduler is already running. Skipping start.")
        return

    _scheduler_lock = True

    try:
        scheduler = BackgroundScheduler()
        scheduler.add_jobstore(DjangoJobStore(), "default")

        ist = pytz.timezone('Asia/Kolkata')

        scheduler.add_job(
            fetch_daily_punch_data_job,
            trigger=CronTrigger(hour=11, minute=0, timezone=ist),
            id="fetch_daily_punch_data_11am",
            name="Fetch Daily Punch Data at 11:00 AM IST",
            replace_existing=True,
        )
        scheduler.add_job(
            fetch_daily_punch_data_job,
            trigger=CronTrigger(hour=15, minute=0, timezone=ist),
            id="fetch_daily_punch_data_3pm",
            name="Fetch Daily Punch Data at 3:00 PM IST",
            replace_existing=True,
        )
        scheduler.add_job(
            fetch_daily_punch_data_job,
            trigger=CronTrigger(hour=23, minute=59, timezone=ist),
            id="fetch_daily_punch_data_1159pm",
            name="Fetch Daily Punch Data at 11:59 PM IST",
            replace_existing=True,
        )

        register_events(scheduler)

        logger.info("Starting APScheduler...")
        scheduler.start()
        _scheduler_instance = scheduler
        logger.info("APScheduler started with 3 daily fetch jobs")

        for job in scheduler.get_jobs():
            logger.info(f"  - {job.id}: {job.name} (next run: {job.next_run_time})")

    except Exception as e:
        logger.error(f"Error configuring scheduler: {str(e)}", exc_info=True)
        raise
    finally:
        _scheduler_lock = False
