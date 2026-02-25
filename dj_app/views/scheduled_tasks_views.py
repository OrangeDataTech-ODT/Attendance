"""
Scheduled task views for external cron job triggers
These endpoints can be called by Render Cron Jobs or external cron services
to execute scheduled tasks when the service is in sleep mode.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.core.management import call_command
from django.core.management.base import CommandError
from django_apscheduler.models import DjangoJobExecution
from django_apscheduler import util
from io import StringIO
import logging
import os
import environ
import sys
import traceback
from django.conf import settings

logger = logging.getLogger(__name__)

# Initialize environment
env = environ.Env()
environ.Env.read_env(os.path.join(settings.BASE_DIR, '.env'))


def verify_cron_token(request):
    """
    Verify the cron token from request headers or query parameters
    Returns True if token is valid, False otherwise
    """
    # Get token from environment variable
    expected_token = env('CRON_SECRET_TOKEN', default='')
    
    # If no token is set, allow access (for development only)
    # In production, always set CRON_SECRET_TOKEN
    if not expected_token:
        logger.warning("CRON_SECRET_TOKEN not set in environment variables. Allowing access.")
        return True
    
    # Check token from Authorization header (Bearer token)
    auth_header = request.META.get('HTTP_AUTHORIZATION', '')
    if auth_header.startswith('Bearer '):
        token = auth_header.split('Bearer ')[1]
        if token == expected_token:
            return True
    
    # Check token from query parameter
    token_param = request.GET.get('token', '')
    if token_param == expected_token:
        return True
    
    return False


class FetchDailyPunchDataAPI(APIView):
    """
    API endpoint to trigger fetch_daily_punch_data command
    This endpoint should be called by cron jobs at:
    - 11:00 AM IST
    - 3:00 PM IST  
    - 11:59 PM IST
    """
    
    def get(self, request):
        """
        Execute the fetch_daily_punch_data management command
        """
        # Verify authentication token
        if not verify_cron_token(request):
            logger.warning("Unauthorized cron job attempt")
            return Response({
                "status": "error",
                "message": "Unauthorized. Invalid or missing cron token."
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        # Capture command output
        output = StringIO()
        error_output = StringIO()
        
        try:
            logger.info("Starting fetch_daily_punch_data via API endpoint")
            
            # Redirect stdout and stderr to capture output
            old_stdout = sys.stdout
            old_stderr = sys.stderr
            sys.stdout = output
            sys.stderr = error_output
            
            try:
                # Execute the command
                call_command('fetch_daily_punch_data', verbosity=2)
            finally:
                # Restore stdout and stderr
                sys.stdout = old_stdout
                sys.stderr = old_stderr
            
            # Get captured output
            command_output = output.getvalue()
            command_errors = error_output.getvalue()
            
            logger.info("Completed fetch_daily_punch_data via API endpoint")
            logger.info(f"Command output: {command_output}")
            
            if command_errors:
                logger.warning(f"Command errors: {command_errors}")
            
            return Response({
                "status": "success",
                "message": "fetch_daily_punch_data command executed successfully",
                "output": command_output,
                "errors": command_errors if command_errors else None
            }, status=status.HTTP_200_OK)
            
        except CommandError as e:
            # Django management command specific error
            error_msg = str(e)
            logger.error(f"CommandError in fetch_daily_punch_data: {error_msg}", exc_info=True)
            return Response({
                "status": "error",
                "message": f"Command error: {error_msg}",
                "output": output.getvalue(),
                "errors": error_output.getvalue()
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
        except Exception as e:
            # General exception
            error_msg = str(e)
            error_traceback = traceback.format_exc()
            logger.error(f"Error in fetch_daily_punch_data API endpoint: {error_msg}", exc_info=True)
            return Response({
                "status": "error",
                "message": error_msg,
                "traceback": error_traceback if settings.DEBUG else None,
                "output": output.getvalue(),
                "errors": error_output.getvalue()
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@util.close_old_connections
def delete_old_job_executions(max_age=604_800):  # 7 days
    """
    Delete old job execution logs to prevent database from filling up
    """
    DjangoJobExecution.objects.delete_old_job_executions(max_age)


class CleanupJobExecutionsAPI(APIView):
    """
    API endpoint to clean up old job execution logs
    This endpoint should be called by cron jobs at:
    - Midnight IST (00:00)
    """
    
    def get(self, request):
        """
        Execute the cleanup of old job executions
        """
        # Verify authentication token
        if not verify_cron_token(request):
            logger.warning("Unauthorized cron job attempt for cleanup")
            return Response({
                "status": "error",
                "message": "Unauthorized. Invalid or missing cron token."
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        try:
            logger.info("Starting cleanup of old job executions via API endpoint")
            delete_old_job_executions()
            logger.info("Completed cleanup of old job executions via API endpoint")
            
            return Response({
                "status": "success",
                "message": "Old job executions cleaned up successfully"
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            error_traceback = traceback.format_exc()
            logger.error(f"Error in cleanup job executions API endpoint: {str(e)}", exc_info=True)
            return Response({
                "status": "error",
                "message": str(e),
                "traceback": error_traceback if settings.DEBUG else None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CronHealthCheckAPI(APIView):
    """
    Simple health check endpoint for cron jobs
    This endpoint can be used to verify the cron service is working
    """
    
    def get(self, request):
        """
        Return a simple success response
        """
        return Response({
            "status": "success",
            "message": "Cron endpoint is working",
            "service": "active"
        }, status=status.HTTP_200_OK)


