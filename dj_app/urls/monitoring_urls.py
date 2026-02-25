from django.urls import path
from ..views.punch_monitoring_views import PunchMonitoringAPI

app_name = 'monitoring'
urlpatterns = [
    path('punch/', PunchMonitoringAPI.as_view(), name='punch_monitoring'),
]

