from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from .api import TrackingViewSet, TrackingShareViewSet, FlightAlertViewSet

router = DefaultRouter()
router.register(r'tracks', TrackingViewSet, basename='track')
router.register(r'shares', TrackingShareViewSet, basename='share')
router.register(r'alerts', FlightAlertViewSet, basename='alert')

app_name = 'tracking'

urlpatterns = [
    # Web URLs
    path('', views.TrackingDashboardView.as_view(), name='dashboard'),
    path('flight/<uuid:booking_id>/', views.FlightTrackingView.as_view(), name='flight_track'),
    path('share/<uuid:token>/', views.SharedTrackingView.as_view(), name='shared'),
    path('history/<uuid:booking_id>/', views.TrackingHistoryView.as_view(), name='history'),
    path('cargo/', views.CargoTrackingView.as_view(), name='cargo_tracking'),
    path('api/cargo/<uuid:track_id>/', views.cargo_status_api, name='api_cargo_status'),
    
    # API URLs
    path('api/', include(router.urls)),
    path('api/position/<uuid:track_id>/', views.update_position, name='api_update_position'),
]