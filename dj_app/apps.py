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
        won't work unless the server stays running.
        Set USE_INTERNAL_SCHEDULER=False to disable the internal scheduler.
        """
        import os
        import sys
        import environ
        from django.conf import settings

        # Skip if running tests, migrations, or collectstatic
        skip_commands = ['test', 'migrate', 'collectstatic', 'makemigrations', 'shell']
        if any(cmd in sys.argv for cmd in skip_commands):
            logger.info(f"Skipping scheduler start for command: {sys.argv}")
            return

        # Django runserver autoreloader: only start in the child process
        if 'runserver' in sys.argv and os.environ.get('RUN_MAIN') != 'true':
            return

        env = environ.Env()
        environ.Env.read_env(os.path.join(settings.BASE_DIR, '.env'))
        use_internal_scheduler = env.bool('USE_INTERNAL_SCHEDULER', default=True)

        if not use_internal_scheduler:
            logger.info("Internal scheduler disabled (USE_INTERNAL_SCHEDULER=False).")
            return

        # Gunicorn: start scheduler only in the worker with RUN_SCHEDULER=1
        if 'gunicorn' in sys.modules:
            if os.environ.get('RUN_SCHEDULER', '0') != '1':
                logger.info("Skipping scheduler in gunicorn worker (RUN_SCHEDULER!=1).")
                return

        try:
            from .scheduler import start_scheduler
            logger.info("Attempting to start internal scheduler...")
            start_scheduler()
            logger.info("Internal scheduler started successfully")
        except Exception as e:
            logger.error(f"Error starting scheduler: {str(e)}", exc_info=True)
            logger.warning("Scheduler failed to start.")
