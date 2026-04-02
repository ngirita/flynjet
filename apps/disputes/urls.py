from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from .api import DisputeViewSet, DisputeMessageViewSet, DisputeResolutionViewSet

router = DefaultRouter()
router.register(r'disputes', DisputeViewSet, basename='dispute')
router.register(r'messages', DisputeMessageViewSet, basename='message')
router.register(r'resolutions', DisputeResolutionViewSet, basename='resolution')

app_name = 'disputes'

urlpatterns = [
    # Web URLs
    path('', views.DisputeListView.as_view(), name='list'),
    path('create/<uuid:booking_id>/', views.CreateDisputeView.as_view(), name='create'),
    path('<uuid:pk>/', views.DisputeDetailView.as_view(), name='detail'),
    path('<uuid:pk>/message/', views.add_message, name='add_message'),
    path('<uuid:pk>/evidence/', views.upload_evidence, name='upload_evidence'),
    
    # Admin URLs
    path('admin/', views.AdminDisputeListView.as_view(), name='admin_list'),
    path('admin/<uuid:pk>/', views.AdminDisputeDetailView.as_view(), name='admin_detail'),
    path('admin/<uuid:pk>/assign/', views.assign_dispute, name='assign'),
    path('admin/<uuid:pk>/resolve/', views.resolve_dispute, name='resolve'),
    
    # API URLs
    path('api/', include(router.urls)),
]