from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.disputes.api import DisputeViewSet, DisputeMessageViewSet, DisputeResolutionViewSet

router = DefaultRouter()
router.register(r'disputes', DisputeViewSet, basename='dispute')
router.register(r'messages', DisputeMessageViewSet, basename='message')
router.register(r'resolutions', DisputeResolutionViewSet, basename='resolution')

urlpatterns = [
    path('', include(router.urls)),
]