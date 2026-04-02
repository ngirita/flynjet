from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.tracking.api import TrackingViewSet, TrackingShareViewSet, FlightAlertViewSet

router = DefaultRouter()
router.register(r'tracks', TrackingViewSet, basename='track')
router.register(r'shares', TrackingShareViewSet, basename='share')
router.register(r'alerts', FlightAlertViewSet, basename='alert')

urlpatterns = [
    path('', include(router.urls)),
]