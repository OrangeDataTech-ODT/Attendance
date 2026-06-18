"""
Manual trigger for fetch_daily_punch_data (optional — scheduler runs this automatically).
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.core.management import call_command
from django.core.management.base import CommandError
from io import StringIO
import logging
import os
import environ
import sys
import traceback
from django.conf import settings

logger = logging.getLogger(__name__)

env = environ.Env()
environ.Env.read_env(os.path.join(settings.BASE_DIR, '.env'))


def verify_cron_token(request):
    expected_token = env('CRON_SECRET_TOKEN', default='')
    if not expected_token:
        return True

    auth_header = request.META.get('HTTP_AUTHORIZATION', '')
    if auth_header.startswith('Bearer '):
        token = auth_header.split('Bearer ')[1]
        if token == expected_token:
            return True

    token_param = request.GET.get('token', '')
    if token_param == expected_token:
        return True

    return False


class FetchDailyPunchDataAPI(APIView):
    """Manually trigger fetch_daily_punch_data (scheduler handles the 3 daily runs)."""

    def get(self, request):
        if not verify_cron_token(request):
            return Response({
                "status": "error",
                "message": "Unauthorized. Invalid or missing cron token."
            }, status=status.HTTP_401_UNAUTHORIZED)

        output = StringIO()
        error_output = StringIO()

        try:
            logger.info("Starting fetch_daily_punch_data via API endpoint")
            old_stdout = sys.stdout
            old_stderr = sys.stderr
            sys.stdout = output
            sys.stderr = error_output

            try:
                call_command('fetch_daily_punch_data', verbosity=2)
            finally:
                sys.stdout = old_stdout
                sys.stderr = old_stderr

            command_output = output.getvalue()
            command_errors = error_output.getvalue()
            logger.info("Completed fetch_daily_punch_data via API endpoint")

            return Response({
                "status": "success",
                "message": "fetch_daily_punch_data command executed successfully",
                "output": command_output,
                "errors": command_errors if command_errors else None
            }, status=status.HTTP_200_OK)

        except CommandError as e:
            return Response({
                "status": "error",
                "message": f"Command error: {str(e)}",
                "output": output.getvalue(),
                "errors": error_output.getvalue()
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        except Exception as e:
            logger.error(f"Error in fetch_daily_punch_data API endpoint: {str(e)}", exc_info=True)
            return Response({
                "status": "error",
                "message": str(e),
                "traceback": traceback.format_exc() if settings.DEBUG else None,
                "output": output.getvalue(),
                "errors": error_output.getvalue()
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
