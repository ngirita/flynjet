from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from .api import APIIntegrationViewSet, WebhookViewSet, WeatherViewSet, FuelPriceViewSet, ExchangeRateViewSet

router = DefaultRouter()
router.register(r'api', APIIntegrationViewSet, basename='api')
router.register(r'webhooks', WebhookViewSet, basename='webhook')
router.register(r'weather', WeatherViewSet, basename='weather')
router.register(r'fuel', FuelPriceViewSet, basename='fuel')
router.register(r'rates', ExchangeRateViewSet, basename='rate')

app_name = 'integrations'

urlpatterns = [
    # Webhook endpoints (public)
    path('webhook/<str:path>/', views.handle_webhook, name='webhook'),
    
    # API URLs
    path('api/', include(router.urls)),
    
    # External data endpoints
    path('weather/<str:location>/', views.get_weather, name='weather'),
    path('fuel/<str:location>/', views.get_fuel_prices, name='fuel'),
    path('exchange/<str:from_currency>/<str:to_currency>/', views.get_exchange_rate, name='exchange'),
]