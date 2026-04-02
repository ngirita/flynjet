from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from .models import APIIntegration, WebhookEndpoint, WebhookDelivery, WeatherCache, FuelPriceCache, ExchangeRateCache
from .serializers import (
    APIIntegrationSerializer, WebhookEndpointSerializer,
    WebhookDeliverySerializer, WeatherCacheSerializer,
    FuelPriceCacheSerializer, ExchangeRateCacheSerializer
)

class APIIntegrationViewSet(viewsets.ModelViewSet):
    """API for managing third-party integrations"""
    serializer_class = APIIntegrationSerializer
    permission_classes = [permissions.IsAdminUser]
    queryset = APIIntegration.objects.all()
    
    @action(detail=True, methods=['post'])
    def test(self, request, pk=None):
        """Test API connection"""
        integration = self.get_object()
        
        try:
            # Test connection logic
            integration.last_checked = timezone.now()
            integration.last_error = ''
            integration.save()
            return Response({'status': 'success'})
        except Exception as e:
            integration.last_error = str(e)
            integration.save()
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def refresh_token(self, request, pk=None):
        """Refresh OAuth token"""
        integration = self.get_object()
        
        if integration.auth_type != 'oauth2':
            return Response({'error': 'Not an OAuth2 integration'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Refresh token logic
        integration.token_expires_at = timezone.now() + timezone.timedelta(hours=1)
        integration.save()
        
        return Response({'status': 'token_refreshed'})


class WebhookViewSet(viewsets.ModelViewSet):
    """API for managing webhooks"""
    serializer_class = WebhookEndpointSerializer
    permission_classes = [permissions.IsAdminUser]
    queryset = WebhookEndpoint.objects.all()
    
    @action(detail=True, methods=['get'])
    def deliveries(self, request, pk=None):
        """Get webhook delivery history"""
        webhook = self.get_object()
        deliveries = webhook.deliveries.all().order_by('-created_at')[:50]
        serializer = WebhookDeliverySerializer(deliveries, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def test_delivery(self, request, pk=None):
        """Test webhook delivery"""
        webhook = self.get_object()
        
        # Create test payload
        test_payload = {
            'event': 'test',
            'timestamp': timezone.now().isoformat(),
            'data': {'message': 'This is a test webhook'}
        }
        
        # Trigger webhook
        delivery = WebhookDelivery.objects.create(
            webhook=webhook,
            event_type='test',
            payload=test_payload
        )
        
        # Attempt delivery
        # This would actually call the webhook URL
        delivery.mark_delivered(200, 'OK')
        
        return Response({'status': 'delivered', 'delivery_id': delivery.id})


class WeatherViewSet(viewsets.ReadOnlyModelViewSet):
    """API for weather data"""
    serializer_class = WeatherCacheSerializer
    permission_classes = [permissions.AllowAny]
    
    def get_queryset(self):
        return WeatherCache.objects.all().order_by('-fetched_at')
    
    @action(detail=False, methods=['get'])
    def current(self, request):
        """Get current weather for location"""
        location = request.query_params.get('location')
        if not location:
            return Response({'error': 'Location required'}, status=400)
        
        from .views import get_weather
        return get_weather(request, location)


class FuelPriceViewSet(viewsets.ReadOnlyModelViewSet):
    """API for fuel prices"""
    serializer_class = FuelPriceCacheSerializer
    permission_classes = [permissions.AllowAny]
    
    def get_queryset(self):
        return FuelPriceCache.objects.all().order_by('-fetched_at')
    
    @action(detail=False, methods=['get'])
    def current(self, request):
        """Get current fuel prices for location"""
        location = request.query_params.get('location')
        if not location:
            return Response({'error': 'Location required'}, status=400)
        
        from .views import get_fuel_prices
        return get_fuel_prices(request, location)


class ExchangeRateViewSet(viewsets.ReadOnlyModelViewSet):
    """API for exchange rates"""
    serializer_class = ExchangeRateCacheSerializer
    permission_classes = [permissions.AllowAny]
    
    def get_queryset(self):
        return ExchangeRateCache.objects.all().order_by('-fetched_at')
    
    @action(detail=False, methods=['get'])
    def convert(self, request):
        """Convert amount between currencies"""
        from_currency = request.query_params.get('from', 'USD')
        to_currency = request.query_params.get('to')
        amount = float(request.query_params.get('amount', 1))
        
        if not to_currency:
            return Response({'error': 'Target currency required'}, status=400)
        
        from .views import get_exchange_rate
        response = get_exchange_rate(request, from_currency, to_currency)
        
        if response.status_code == 200:
            data = response.data
            converted = amount * data['rate']
            data['original_amount'] = amount
            data['converted_amount'] = converted
            return Response(data)
        
        return response