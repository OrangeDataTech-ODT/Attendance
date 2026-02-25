
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static


urlpatterns = [
    path('mcid/', include('dj_app.urls.data_with_mcid_urls', namespace='mcid')),
    path('inout/', include('dj_app.urls.inout_punch_urls', namespace='inout')),
    path('files/', include('dj_app.urls.process_file_urls', namespace='files')),
    path('mcid-data/', include('dj_app.urls.mcid_data_urls', namespace='mcid-data')),
    path('monitor/', include('dj_app.urls.monitoring_urls', namespace='monitoring')),
    path('cron/', include('dj_app.urls.scheduled_tasks_urls', namespace='scheduled_tasks')),
    path('email/', include('dj_app.urls.email_urls', namespace='email')),
]
