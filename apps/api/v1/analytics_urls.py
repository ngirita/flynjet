from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.analytics.api import AnalyticsEventViewSet, DailyMetricViewSet, ReportViewSet, DashboardViewSet

router = DefaultRouter()
router.register(r'events', AnalyticsEventViewSet, basename='event')
router.register(r'metrics', DailyMetricViewSet, basename='metric')
router.register(r'reports', ReportViewSet, basename='report')
router.register(r'dashboards', DashboardViewSet, basename='dashboard')

urlpatterns = [
    path('', include(router.urls)),
]