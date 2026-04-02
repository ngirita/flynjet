from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from .api import ConsentViewSet, DataSubjectRequestViewSet, BreachNotificationViewSet

router = DefaultRouter()
router.register(r'consent', ConsentViewSet, basename='consent')
router.register(r'dsr', DataSubjectRequestViewSet, basename='dsr')
router.register(r'breaches', BreachNotificationViewSet, basename='breach')

app_name = 'compliance'

urlpatterns = [
    # Web URLs
    path('consent/', views.ConsentManagementView.as_view(), name='consent'),
    path('dsr/', views.DataSubjectRequestView.as_view(), name='dsr'),
    path('dsr/<uuid:pk>/', views.DataSubjectRequestDetailView.as_view(), name='dsr_detail'),
    path('cookie-consent/', views.cookie_consent, name='cookie_consent'),
    path('data-export/', views.request_data_export, name='data_export'),
    path('account-deletion/', views.request_account_deletion, name='account_deletion'),
    
    # API URLs
    path('api/', include(router.urls)),
]