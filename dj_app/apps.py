from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)


class DjAppConfig(AppConfig):
    name = 'dj_app'
    
    def ready(self):
        """
        Start the scheduler when Django starts
        This method is called when the app is ready
        
        Note: On Render free tier, services spin down when inactive, so the scheduler
        won't work. Use external cron jobs (Render Cron Jobs or external services)
        to call the /cron/ endpoints instead.
        Set USE_INTERNAL_SCHEDULER=False to disable the internal scheduler.
        """
        import os
        import environ
        from django.conf import settings
        
        # Check if we should start the scheduler
        # Skip if running tests, migrations, or collectstatic
        skip_commands = ['test', 'migrate', 'collectstatic', 'makemigrations', 'shell']
        if any(cmd in os.sys.argv for cmd in skip_commands):
            logger.info(f"Skipping scheduler start for command: {os.sys.argv}")
            return
        
        # Check if internal scheduler should be used
        # If USE_INTERNAL_SCHEDULER is False, we'll use external cron jobs instead
        env = environ.Env()
        environ.Env.read_env(os.path.join(settings.BASE_DIR, '.env'))
        use_internal_scheduler = env.bool('USE_INTERNAL_SCHEDULER', default=True)
        
        if not use_internal_scheduler:
            logger.info("Internal scheduler disabled. Using external cron jobs instead.")
            logger.info("To use internal scheduler, set USE_INTERNAL_SCHEDULER=True")
            return
        
        # Only start scheduler in the main process (not in worker processes)
        # This prevents multiple schedulers from running
        try:
            # Check if we're in a worker process (e.g., gunicorn worker)
            # In production, only start scheduler in the main/master process
            import sys
            is_main_process = True
            
            # For gunicorn, only start in master process
            if 'gunicorn' in sys.modules:
                try:
                    from gunicorn.arbiter import Arbiter
                    # If we can import Arbiter, we're likely in a worker
                    # The master process will handle this differently
                    is_main_process = os.environ.get('SERVER_SOFTWARE', '').startswith('gunicorn')
                except ImportError:
                    pass
            
            if not is_main_process:
                logger.info("Skipping scheduler start in worker process")
                return
            
            from .scheduler import start_scheduler
            logger.info("Attempting to start internal scheduler...")
            start_scheduler()
            logger.info("Internal scheduler started successfully")
        except Exception as e:
            logger.error(f"Error starting scheduler: {str(e)}", exc_info=True)
            logger.warning("Scheduler failed to start. Consider using external cron jobs instead.")
            logger.warning("Set USE_INTERNAL_SCHEDULER=False and use /cron/ endpoints with external cron services.")
