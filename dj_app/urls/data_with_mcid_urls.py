from django.urls import path
from django.contrib import admin
from ..views.data_with_mcid_views import (
    FetchPunchData, 
    FetchPunchDataWithParams, 
    FetchEmployeePunchData,
)

app_name='mcid'
urlpatterns=[
    #export mcid data to a csv file and save to database
    path('export/', FetchPunchData.as_view(), name='export'),
    #fetch a single record by id
    path('record/', FetchPunchDataWithParams.as_view(), name='record'),
    #fetch multiple records
    path('records/', FetchEmployeePunchData.as_view(), name='records')
]