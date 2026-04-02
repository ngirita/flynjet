from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model
from .models import APIIntegration, WebhookEndpoint, WeatherCache

User = get_user_model()

class IntegrationsModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
    
    def test_create_api_integration(self):
        api = APIIntegration.objects.create(
            name='Test API',
            integration_type='weather',
            base_url='https://api.test.com',
            auth_type='api_key',
            api_key='test-key'
        )
        
        self.assertEqual(api.name, 'Test API')
        self.assertEqual(api.integration_type, 'weather')
        self.assertTrue(api.is_active)
    
    def test_create_webhook(self):
        webhook = WebhookEndpoint.objects.create(
            name='Test Webhook',
            path='test-webhook',
            secret='test-secret',
            handler_function='apps.integrations.handlers.test_handler'
        )
        
        self.assertEqual(webhook.path, 'test-webhook')
        self.assertTrue(webhook.require_signature)
    
    def test_weather_cache(self):
        weather = WeatherCache.objects.create(
            location_key='JFK',
            latitude=40.6413,
            longitude=-73.7781,
            temperature=22.5,
            feels_like=21.0,
            humidity=65,
            pressure=1013,
            wind_speed=5.2,
            wind_direction=180,
            conditions='Clear sky',
            icon='01d',
            expires_at=timezone.now() + timezone.timedelta(hours=1)
        )
        
        self.assertEqual(weather.location_key, 'JFK')
        self.assertEqual(weather.temperature, 22.5)
        self.assertFalse(weather.is_expired())

class IntegrationsViewsTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.webhook = WebhookEndpoint.objects.create(
            name='Test Webhook',
            path='test-webhook',
            secret='test-secret',
            handler_function='apps.integrations.handlers.test_handler'
        )
    
    def test_webhook_endpoint(self):
        response = self.client.post(
            '/integrations/webhook/test-webhook/',
            data={'test': 'data'},
            content_type='application/json',
            HTTP_X_SIGNATURE='test-signature'
        )
        
        # Should return 401 due to invalid signature
        self.assertEqual(response.status_code, 401)
    
    def test_weather_api(self):
        response = self.client.get('/integrations/weather/JFK/')
        self.assertEqual(response.status_code, 200)
    
    def test_exchange_rate_api(self):
        response = self.client.get('/integrations/exchange/USD/EUR/')
        self.assertEqual(response.status_code, 200)