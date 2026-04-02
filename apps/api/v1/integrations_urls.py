from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.integrations.api import APIIntegrationViewSet, WebhookViewSet, WeatherViewSet, FuelPriceViewSet, ExchangeRateViewSet

router = DefaultRouter()
router.register(r'api', APIIntegrationViewSet, basename='api')
router.register(r'webhooks', WebhookViewSet, basename='webhook')
router.register(r'weather', WeatherViewSet, basename='weather')
router.register(r'fuel', FuelPriceViewSet, basename='fuel')
router.register(r'rates', ExchangeRateViewSet, basename='rate')

urlpatterns = [
    path('', include(router.urls)),
]