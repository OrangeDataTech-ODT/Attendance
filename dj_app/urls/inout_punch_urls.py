from django.urls import path
from ..views.all_data_views import (
    FetchInOutPunchDataAll,
    FetchInOutPunchDataSelective,
    FetchInOutPunchData,
    FetchAndStorePunchDataAPI,
    RetrieveStoredPunchDataAPI
)

app_name = 'inout'
urlpatterns = [
    #fetch all inout punch data
    path('list/', FetchInOutPunchDataAll.as_view(), name='list'),
    #fetch a single employee inout punch data
    path('filter/', FetchInOutPunchDataSelective.as_view(), name='filter'),
    #fetch inout punch data for a single or multiple employees
    path('search/', FetchInOutPunchData.as_view(), name='search'),
    #fetch and store punch data with date range (manual)
    path('fetch-and-store/', FetchAndStorePunchDataAPI.as_view(), name='fetch_and_store'),
    #retrieve stored punch data from database with date range and optional empcode
    path('retrieve/', RetrieveStoredPunchDataAPI.as_view(), name='retrieve'),
]

