from django.urls import path
from . import views

app_name = 'airports'

urlpatterns = [
    path('', views.AirportListView.as_view(), name='list'),
    path('autocomplete/', views.AirportAutocompleteView.as_view(), name='autocomplete'),
    path('<str:iata_code>/', views.AirportDetailView.as_view(), name='detail'),
]