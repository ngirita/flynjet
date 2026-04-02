from rest_framework import serializers
from .models import APIIntegration, WebhookEndpoint, WebhookDelivery, WeatherCache, FuelPriceCache, ExchangeRateCache

class APIIntegrationSerializer(serializers.ModelSerializer):
    class Meta:
        model = APIIntegration
        fields = [
            'id', 'name', 'integration_type', 'base_url', 'auth_type',
            'is_active', 'last_checked', 'last_error', 'config'
        ]
        read_only_fields = ['last_checked', 'last_error']


class WebhookEndpointSerializer(serializers.ModelSerializer):
    delivery_count = serializers.SerializerMethodField()
    
    class Meta:
        model = WebhookEndpoint
        fields = [
            'id', 'name', 'path', 'is_active', 'events',
            'require_signature', 'allowed_ips', 'delivery_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['path', 'created_at', 'updated_at']
    
    def get_delivery_count(self, obj):
        return obj.deliveries.count()


class WebhookDeliverySerializer(serializers.ModelSerializer):
    webhook_name = serializers.CharField(source='webhook.name', read_only=True)
    
    class Meta:
        model = WebhookDelivery
        fields = [
            'id', 'webhook', 'webhook_name', 'event_type',
            'status', 'attempts', 'last_attempt', 'response_status',
            'created_at'
        ]
        read_only_fields = ['created_at']


class WeatherCacheSerializer(serializers.ModelSerializer):
    class Meta:
        model = WeatherCache
        fields = '__all__'
        read_only_fields = ['fetched_at']


class FuelPriceCacheSerializer(serializers.ModelSerializer):
    class Meta:
        model = FuelPriceCache
        fields = '__all__'
        read_only_fields = ['fetched_at']


class ExchangeRateCacheSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExchangeRateCache
        fields = '__all__'
        read_only_fields = ['fetched_at']