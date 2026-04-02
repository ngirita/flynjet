from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.fleet.api import AircraftViewSet, CategoryViewSet

router = DefaultRouter()
router.register(r'aircraft', AircraftViewSet)
router.register(r'categories', CategoryViewSet)

urlpatterns = [
    path('', include(router.urls)),
]