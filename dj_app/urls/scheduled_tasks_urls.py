from django.urls import path
from ..views.scheduled_tasks_views import FetchDailyPunchDataAPI

app_name = 'scheduled_tasks'
urlpatterns = [
    path('fetch-daily-punch-data/', FetchDailyPunchDataAPI.as_view(), name='fetch_daily_punch_data'),
]
