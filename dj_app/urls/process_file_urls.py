from django.urls import path
from django.contrib import admin
from ..views.process_file_views import ( 
    GetAllPunchDataFiles,
    GetPunchDataFileById,
    ProcessPunchDataOperations
)

app_name='operate_file'
urlpatterns=[
    path('list/', GetAllPunchDataFiles.as_view(), name='list'),
    path('detail/<int:file_id>/', GetPunchDataFileById.as_view(), name='detail'),
    path('process/<int:file_id>/', ProcessPunchDataOperations.as_view(), name='process'),
]