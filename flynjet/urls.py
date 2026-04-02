# flynjet/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView

# Phase 2 imports
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from two_factor.urls import urlpatterns as tf_urls

# Import your custom health check view
from apps.core.views import health_check

# API Documentation
schema_view = get_schema_view(
    openapi.Info(
        title="FlynJet API",
        default_version='v1',
        description="API for FlynJet Private Jet Charter Platform",
        terms_of_service="https://www.flynjet.com/terms/",
        contact=openapi.Contact(email="info@flynjet.com"),
        license=openapi.License(name="Proprietary"),
    ),
    public=True,
    permission_classes=[permissions.AllowAny],
)

urlpatterns = [
    # ========== CRITICAL: Core URLs FIRST to catch /admin/api/ ==========
    path('', include('apps.core.urls')),  # <-- MOVED TO TOP
    
    # Admin
    path('admin/', admin.site.urls),
    
    # Two Factor Authentication
    path('account/', include(tf_urls)),
    
    # API Documentation
    path('api/docs/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('api/redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
    path('api/json/', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    
    # API v1 & v2
    path('api/v1/', include('apps.api.v1.urls')),
    path('api/v2/', include('apps.api.v2.urls')),
    
    # Allauth - for social login (Facebook, Google, LinkedIn)
    path('accounts/', include('allauth.urls')),
    
    # Your custom accounts - use 'auth/' to avoid conflict with allauth
    path('auth/', include('apps.accounts.urls')),
    
    # Airports app URLs
    path('airports/', include('apps.airports.urls')),
    
    # App URLs
    path('bookings/', include('apps.bookings.urls')),
    path('payments/', include('apps.payments.urls')),
    path('fleet/', include('apps.fleet.urls')),
    path('tracking/', include('apps.tracking.urls')),
    path('chat/', include('apps.chat.urls')),
    path('documents/', include('apps.documents.urls')),
    path('reviews/', include('apps.reviews.urls')),
    path('disputes/', include('apps.disputes.urls')),
    path('marketing/', include('apps.marketing.urls')),
    path('analytics/', include('apps.analytics.urls')),
    path('compliance/', include('apps.compliance.urls')),
    path('integrations/', include('apps.integrations.urls')),
    
    # Health check
    path('health/', health_check, name='health_check'),
    
    # Prometheus metrics
    path('', include('django_prometheus.urls')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    
    # Debug toolbar
    import debug_toolbar
    urlpatterns += [
        path('__debug__/', include(debug_toolbar.urls)),
    ]

# Custom error handlers
handler404 = 'apps.core.views.handler404'
handler500 = 'apps.core.views.handler500'
handler403 = 'apps.core.views.handler403'
handler400 = 'apps.core.views.handler400'