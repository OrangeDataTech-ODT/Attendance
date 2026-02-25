"""
Django APScheduler configuration
This file sets up scheduled jobs that run automatically

IMPORTANT DEPLOYMENT NOTES:
==========================

1. On Render.com FREE tier, services spin down after 15 minutes of inactivity.
   When the service is sleeping, the scheduler process is not running, so scheduled
   jobs will NOT execute. Use external cron jobs (cron-job.org, etc.) to call
   the /cron/ endpoints instead.

2. Set USE_INTERNAL_SCHEDULER=False in environment variables to disable the
   internal scheduler and use external cron jobs.

3. For production with multiple worker processes (Gunicorn), the scheduler
   should only start in the main process. The code includes safeguards to prevent
   multiple schedulers from starting.

4. If using internal scheduler, ensure the service stays awake by pinging the
   /cron/health/ endpoint every 10 minutes using an external service.

See SCHEDULER_TROUBLESHOOTING.md for detailed troubleshooting guide.
"""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from django_apscheduler.jobstores import DjangoJobStore, register_events
from django_apscheduler.models import DjangoJobExecution
from django_apscheduler import util
from django.utils import timezone
import logging
import pytz
import requests

logger = logging.getLogger(__name__)


def fetch_daily_punch_data_job():
    """
    Scheduled job to fetch and save punch data for the current day
    Runs at 11:00 AM, 3:00 PM, and 11:59 PM IST
    """
    from django.core.management import call_command
    
    try:
        logger.info("Starting scheduled fetch_daily_punch_data job")
        call_command('fetch_daily_punch_data')
        logger.info("Completed scheduled fetch_daily_punch_data job")
    except Exception as e:
        logger.error(f"Error in scheduled fetch_daily_punch_data job: {str(e)}", exc_info=True)


def fetch_id_only_job():
    """
    Scheduled job to call the id_only fetch API for today's data.
    Maps to endpoint: /mcid-data/fetch/?from_date=DD/MM/YYYY&to_date=DD/MM/YYYY
    """
    import os
    try:
        logger.info("Starting scheduled id_only fetch job")
        today_str = timezone.localdate().strftime('%d/%m/%Y')
        params = {
            'from_date': today_str,
            'to_date': today_str,
        }
        # test_date = '20/01/2026'   # put any date you want to test
        # params = {
        #     'from_date': test_date,
        #     'to_date': test_date,
        # }
        
        # Use environment variable for base URL, fallback to localhost for local development
        base_url = os.getenv('RENDER_EXTERNAL_URL', 'https://check-your-time.onrender.com')
        api_url = f"{base_url}/mcid-data/fetch/"

        response = requests.get(
            api_url,
            params=params,
            timeout=300,
        )
        logger.info(
            "Completed id_only fetch job with status %s and response: %s",
            response.status_code,
            response.text[:1000],
        )
    except Exception as e:
        logger.error(f"Error in scheduled id_only fetch job: {str(e)}", exc_info=True)


def process_id_only_job():
    """
    Scheduled job to call the id_only process API for today's data.
    Maps to endpoint: /mcid-data/process/?from_date=DD/MM/YYYY&to_date=DD/MM/YYYY
    """
    import os
    try:
        logger.info("Starting scheduled id_only process job")
        today_str = timezone.localdate().strftime('%d/%m/%Y')
        params = {
            'from_date': today_str,
            'to_date': today_str,
        }
        # test_date = '20/01/2026'   # put any date you want to test
        # params = {
        #     'from_date': test_date,
        #     'to_date': test_date,
        # }
        
        # Use environment variable for base URL, fallback to localhost for local development
        base_url = os.getenv('RENDER_EXTERNAL_URL', 'https://check-your-time.onrender.com')
        api_url = f"{base_url}/mcid-data/process/"

        response = requests.get(
            api_url,
            params=params,
            timeout=300,
        )
        logger.info(
            "Completed id_only process job with status %s and response: %s",
            response.status_code,
            response.text[:1000],
        )
    except Exception as e:
        logger.error(f"Error in scheduled id_only process job: {str(e)}", exc_info=True)


def keep_alive_job():
    """
    Keep-alive job to ping the health endpoint to prevent Render.com from sleeping
    This job pings the health check endpoint to keep the service active
    Note: This only works when the service is already awake. For keeping it awake,
    use external services (cron-job.org, UptimeRobot) to ping the health endpoint.
    """
    import os
    try:
        # Get the base URL from environment or use default
        # On Render, set RENDER_EXTERNAL_URL=https://check-your-time.onrender.com
        base_url = os.getenv('RENDER_EXTERNAL_URL', 'https://check-your-time.onrender.com')
        health_url = f"{base_url}/cron/health/"
        
        response = requests.get(health_url, timeout=10)
        logger.info(f"Keep-alive ping successful: {response.status_code}")
        return True
    except Exception as e:
        logger.warning(f"Keep-alive ping failed (this is normal if service is sleeping): {str(e)}")
        return False


def monitor_punches_job():
    """
    Scheduled job to monitor punch data and send email notifications
    - Checks for employees who went out (mcid=1) and haven't returned within 30 minutes
    - Sends reminder emails to employees
    - Validates punch patterns and sends notifications for invalid punches
    """
    from django.core.management import call_command
    
    try:
        logger.info("Starting scheduled monitor_punches job")
        call_command('monitor_punches')
        logger.info("Completed scheduled monitor_punches job")
    except Exception as e:
        logger.error(f"Error in scheduled monitor_punches job: {str(e)}", exc_info=True)


@util.close_old_connections
def delete_old_job_executions(max_age=604_800):  # 7 days
    """
    Delete old job execution logs to prevent database from filling up
    """
    DjangoJobExecution.objects.delete_old_job_executions(max_age)


# Global variable to track if scheduler is already running
_scheduler_instance = None
_scheduler_lock = False


def start_scheduler():
    """
    Start the APScheduler with configured jobs
    This function ensures only one scheduler instance runs per process
    """
    global _scheduler_instance, _scheduler_lock
    
    # Prevent multiple schedulers from starting
    if _scheduler_lock:
        logger.warning("Scheduler is already starting. Skipping duplicate start.")
        return
    
    # Check if scheduler is already running
    if _scheduler_instance is not None and _scheduler_instance.running:
        logger.info("Scheduler is already running. Skipping start.")
        return
    
    _scheduler_lock = True
    
    try:
        scheduler = BackgroundScheduler()
        scheduler.add_jobstore(DjangoJobStore(), "default")
        
        # IST timezone
        ist = pytz.timezone('Asia/Kolkata')
        
        # Schedule job to run at 11:00 AM IST daily
        scheduler.add_job(
            fetch_daily_punch_data_job,
            trigger=CronTrigger(hour=11, minute=00, timezone=ist),
            id="fetch_daily_punch_data_11am",
            name="Fetch Daily Punch Data at 11:00 AM IST",
            replace_existing=True,
        )
        logger.info("Scheduled job: fetch_daily_punch_data_11am (11:00 AM IST)")
        
        # Schedule job to run at 3:00 PM IST daily
        scheduler.add_job(
            fetch_daily_punch_data_job,
            trigger=CronTrigger(hour=15, minute=0, timezone=ist),
            id="fetch_daily_punch_data_3pm",
            name="Fetch Daily Punch Data at 3:00 PM IST",
            replace_existing=True,
        )
        logger.info("Scheduled job: fetch_daily_punch_data_3pm (3:00 PM IST)")
        
        # Schedule job to run at 11:59 PM IST daily
        scheduler.add_job(
            fetch_daily_punch_data_job,
            trigger=CronTrigger(hour=23, minute=59, timezone=ist),
            id="fetch_daily_punch_data_1159pm",
            name="Fetch Daily Punch Data at 11:59 PM IST",
            replace_existing=True,
        )
        logger.info("Scheduled job: fetch_daily_punch_data_1159pm (11:59 PM IST)")
        
        # Schedule cleanup job to run daily at midnight IST
        scheduler.add_job(
            delete_old_job_executions,
            trigger=CronTrigger(hour=0, minute=0, timezone=ist),
            id="delete_old_job_executions",
            name="Delete Old Job Executions",
            replace_existing=True,
        )
        logger.info("Scheduled job: delete_old_job_executions (Midnight IST)")

        # Schedule id_only fetch API at 23:50 IST daily
        scheduler.add_job(
            fetch_id_only_job,
            trigger=CronTrigger(hour=23, minute=50, timezone=ist),
            id="id_only_fetch_2350",
            name="ID-only fetch at 23:50 IST",
            replace_existing=True,
        )
        logger.info("Scheduled job: id_only_fetch_2350 (23:50 IST)")

        # Schedule id_only process API shortly after fetch (23:58 IST daily)
        scheduler.add_job(
            process_id_only_job,
            trigger=CronTrigger(hour=23, minute=58, timezone=ist),
            id="id_only_process_2358",
            name="ID-only process at 23:58 IST",
            replace_existing=True,
        )
        logger.info("Scheduled job: id_only_process_2358 (23:58 IST)")
        
        # Schedule punch monitoring job to run every 30 minutes (checks for missing return punches)
        # This sends emails to employees who went out (mcid=1) and haven't returned within 30 minutes
        # scheduler.add_job(
        #     monitor_punches_job,
        #     trigger=CronTrigger(minute='*/30', timezone=ist),  # Every 30 minutes
        #     id="monitor_punches_30min",
        #     name="Monitor Punches - Check Missing Return Punches",
        #     replace_existing=True,
        # )
        
        # Schedule keep-alive job to run every 10 minutes (only works when service is awake)
        # Note: For Render.com, use external cron jobs to ping the health endpoint
        scheduler.add_job(
            keep_alive_job,
            trigger=CronTrigger(minute='*/10', timezone=ist),  # Every 10 minutes
            id="keep_alive_5min",
            name="Keep Alive - Ping Health Endpoint",
            replace_existing=True,
        )
        logger.info("Scheduled job: keep_alive_5min (Every 10 minutes)")
        
        # Clean up orphaned job executions after all jobs are registered
        # This prevents warnings about jobs that no longer exist
        # The jobs are saved to the database when add_job is called with replace_existing=True
        try:
            from django_apscheduler.models import DjangoJob, DjangoJobExecution
            # Get all job IDs that actually exist in the database
            existing_job_ids = set(DjangoJob.objects.values_list('id', flat=True))
            
            if existing_job_ids:
                # Delete execution records for jobs that don't exist
                orphaned_executions = DjangoJobExecution.objects.exclude(job_id__in=existing_job_ids)
                count = orphaned_executions.count()
                if count > 0:
                    orphaned_executions.delete()
                    logger.info(f"Cleaned up {count} orphaned job execution records for non-existent jobs")
            else:
                # If no jobs exist yet, clean up all old executions (fresh start scenario)
                old_executions = DjangoJobExecution.objects.all()
                count = old_executions.count()
                if count > 0:
                    old_executions.delete()
                    logger.info(f"Cleaned up {count} old job execution records (fresh scheduler start)")
        except Exception as e:
            logger.warning(f"Error cleaning up orphaned job executions: {str(e)}")
            # Continue anyway - this is not critical
        
        register_events(scheduler)
        
        try:
            logger.info("Starting APScheduler...")
            scheduler.start()
            _scheduler_instance = scheduler
            logger.info("APScheduler started successfully with all jobs registered")
            
            # Log all registered jobs
            jobs = scheduler.get_jobs()
            logger.info(f"Total jobs registered: {len(jobs)}")
            for job in jobs:
                logger.info(f"  - {job.id}: {job.name} (next run: {job.next_run_time})")
                
        except Exception as e:
            logger.error(f"Error starting APScheduler: {str(e)}", exc_info=True)
            _scheduler_lock = False
            raise
        finally:
            _scheduler_lock = False
            
    except Exception as e:
        logger.error(f"Error configuring scheduler: {str(e)}", exc_info=True)
        _scheduler_lock = False
        raise

