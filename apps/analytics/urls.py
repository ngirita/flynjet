from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from .api import AnalyticsEventViewSet, DailyMetricViewSet, ReportViewSet, DashboardViewSet

router = DefaultRouter()
router.register(r'events', AnalyticsEventViewSet, basename='event')
router.register(r'metrics', DailyMetricViewSet, basename='metric')
router.register(r'reports', ReportViewSet, basename='report')
router.register(r'dashboards', DashboardViewSet, basename='dashboard')

app_name = 'analytics'

urlpatterns = [
    # Web URLs
    path('dashboard/', views.AnalyticsDashboardView.as_view(), name='dashboard'),
    path('reports/', views.ReportListView.as_view(), name='reports'),
    path('reports/create/', views.CreateReportView.as_view(), name='create_report'),
    path('reports/<uuid:pk>/', views.ReportDetailView.as_view(), name='report_detail'),
    path('reports/<uuid:pk>/download/', views.download_report, name='download_report'),
    path('reports/<uuid:pk>/schedule/', views.schedule_report, name='schedule_report'),
    
    # API URLs
    path('api/', include(router.urls)),
    path('api/track/', views.track_event, name='track_event'),
]