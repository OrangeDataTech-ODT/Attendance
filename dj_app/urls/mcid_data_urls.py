from django.urls import path
from ..views.mcid_data_views import FetchPunchData, ProcessMCIDDataOperations


app_name='id_only'
urlpatterns = [
    path('fetch/', FetchPunchData.as_view(), name='fetch'),
    path('process/', ProcessMCIDDataOperations.as_view(), name='process'),
]