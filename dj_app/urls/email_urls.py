from django.urls import path
from ..views.email_views import SendAttendanceEmailAPI

app_name = 'email'
urlpatterns = [
    path('send-attendance/', SendAttendanceEmailAPI.as_view(), name='send_attendance_email'),
]

