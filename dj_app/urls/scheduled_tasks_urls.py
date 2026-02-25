from django.urls import path
from ..views.scheduled_tasks_views import (
    FetchDailyPunchDataAPI,
    CleanupJobExecutionsAPI,
    CronHealthCheckAPI
)

app_name = 'scheduled_tasks'
urlpatterns = [
    path('health/', CronHealthCheckAPI.as_view(), name='cron_health_check'),
    path('fetch-daily-punch-data/', FetchDailyPunchDataAPI.as_view(), name='fetch_daily_punch_data'),
    path('cleanup-job-executions/', CleanupJobExecutionsAPI.as_view(), name='cleanup_job_executions'),
]


