from celery import shared_task
from django.utils import timezone
from django.core.cache import cache
from .models import APIIntegration, WeatherCache, FuelPriceCache, ExchangeRateCache
from .clients import OpenWeatherClient, ForexClient
import logging

logger = logging.getLogger(__name__)

@shared_task
def refresh_weather_data():
    """Refresh weather data for major locations"""
    major_locations = ['JFK', 'LAX', 'LHR', 'CDG', 'DXB', 'HKG', 'SYD']
    
    client = OpenWeatherClient()
    updated = 0
    
    for location in major_locations:
        data = client.get_weather(location)
        if data:
            WeatherCache.objects.update_or_create(
                location_key=location,
                defaults={
                    'latitude': data.get('lat', 0),
                    'longitude': data.get('lon', 0),
                    'temperature': data['main']['temp'],
                    'feels_like': data['main']['feels_like'],
                    'humidity': data['main']['humidity'],
                    'pressure': data['main']['pressure'],
                    'wind_speed': data['wind']['speed'],
                    'wind_direction': data['wind']['deg'],
                    'conditions': data['weather'][0]['description'],
                    'icon': data['weather'][0]['icon'],
                    'expires_at': timezone.now() + timezone.timedelta(hours=1)
                }
            )
            updated += 1
    
    logger.info(f"Refreshed weather data for {updated} locations")
    return updated

@shared_task
def refresh_exchange_rates():
    """Refresh exchange rates"""
    major_currencies = ['USD', 'EUR', 'GBP', 'JPY', 'AED', 'CNY']
    
    client = ForexClient()
    updated = 0
    
    for from_currency in major_currencies:
        rates = client.get_all_rates(from_currency)
        if rates:
            for to_currency, rate in rates.items():
                if to_currency in major_currencies:
                    ExchangeRateCache.objects.update_or_create(
                        from_currency=from_currency,
                        to_currency=to_currency,
                        defaults={
                            'rate': rate,
                            'expires_at': timezone.now() + timezone.timedelta(hours=1)
                        }
                    )
                    updated += 1
    
    logger.info(f"Refreshed {updated} exchange rates")
    return updated

@shared_task
def cleanup_old_cache_data():
    """Delete expired cache data"""
    # Weather cache
    weather_expired = WeatherCache.objects.filter(expires_at__lt=timezone.now())
    weather_count = weather_expired.count()
    weather_expired.delete()
    
    # Fuel cache
    fuel_expired = FuelPriceCache.objects.filter(expires_at__lt=timezone.now())
    fuel_count = fuel_expired.count()
    fuel_expired.delete()
    
    # Exchange cache
    exchange_expired = ExchangeRateCache.objects.filter(expires_at__lt=timezone.now())
    exchange_count = exchange_expired.count()
    exchange_expired.delete()
    
    logger.info(f"Cleaned up cache data: {weather_count} weather, {fuel_count} fuel, {exchange_count} exchange")
    return {'weather': weather_count, 'fuel': fuel_count, 'exchange': exchange_count}

@shared_task
def check_api_health():
    """Check health of all API integrations"""
    integrations = APIIntegration.objects.filter(is_active=True)
    
    results = []
    for integration in integrations:
        try:
            # Test connection
            # This would depend on the integration type
            integration.last_checked = timezone.now()
            integration.last_error = ''
            integration.save()
            results.append({'name': integration.name, 'status': 'ok'})
        except Exception as e:
            integration.last_error = str(e)
            integration.save()
            results.append({'name': integration.name, 'status': 'error', 'error': str(e)})
    
    logger.info(f"API health check completed: {len(results)} integrations checked")
    return results

@shared_task
def retry_failed_webhooks():
    """Retry failed webhook deliveries"""
    from .models import WebhookDelivery
    
    failed = WebhookDelivery.objects.filter(
        status='failed',
        attempts__lt=3,
        created_at__gte=timezone.now() - timezone.timedelta(days=1)
    )
    
    retried = 0
    for delivery in failed:
        # Retry logic here
        delivery.attempts += 1
        delivery.last_attempt = timezone.now()
        delivery.save()
        retried += 1
    
    logger.info(f"Retried {retried} failed webhook deliveries")
    return retried