import json
import hmac
import hashlib
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.core.cache import cache
from django.utils import timezone
from .models import APIIntegration, WebhookEndpoint, WebhookDelivery, WeatherCache, FuelPriceCache, ExchangeRateCache
from .clients import OpenWeatherClient, AviationStackClient, ForexClient
import logging

logger = logging.getLogger(__name__)

@csrf_exempt
@require_POST
def handle_webhook(request, path):
    """Handle incoming webhook requests"""
    try:
        # Find webhook endpoint
        webhook = get_object_or_404(WebhookEndpoint, path=path, is_active=True)
        
        # Verify signature if required
        if webhook.require_signature:
            signature = request.headers.get('X-Signature', '')
            if not webhook.verify_signature(request.body, signature):
                logger.warning(f"Invalid signature for webhook {path}")
                return HttpResponse(status=401)
        
        # Check IP whitelist
        if webhook.allowed_ips:
            client_ip = request.META.get('REMOTE_ADDR')
            if client_ip not in webhook.allowed_ips:
                logger.warning(f"IP {client_ip} not allowed for webhook {path}")
                return HttpResponse(status=403)
        
        # Parse payload
        try:
            payload = json.loads(request.body)
        except json.JSONDecodeError:
            payload = request.body.decode('utf-8')
        
        # Create delivery record
        delivery = WebhookDelivery.objects.create(
            webhook=webhook,
            event_type=request.headers.get('X-Event-Type', 'unknown'),
            payload=payload
        )
        
        # Process webhook
        try:
            # Call handler function dynamically
            handler_path = webhook.handler_function.split('.')
            module = __import__('.'.join(handler_path[:-1]), fromlist=[handler_path[-1]])
            handler = getattr(module, handler_path[-1])
            result = handler(payload, request.headers)
            
            delivery.mark_delivered(200, json.dumps(result))
            logger.info(f"Webhook {path} processed successfully")
            
            return JsonResponse({'status': 'success', 'data': result})
            
        except Exception as e:
            delivery.mark_failed(str(e))
            logger.error(f"Error processing webhook {path}: {e}")
            return JsonResponse({'error': str(e)}, status=500)
            
    except WebhookEndpoint.DoesNotExist:
        logger.warning(f"Webhook endpoint {path} not found")
        return HttpResponse(status=404)


def get_weather(request, location):
    """Get weather for location"""
    # Check cache first
    cache_key = f"weather_{location}"
    cached = cache.get(cache_key)
    if cached:
        return JsonResponse(cached)
    
    # Try database cache
    try:
        weather_cache = WeatherCache.objects.get(location_key=location)
        if not weather_cache.is_expired():
            data = {
                'location': location,
                'temperature': weather_cache.temperature,
                'feels_like': weather_cache.feels_like,
                'humidity': weather_cache.humidity,
                'pressure': weather_cache.pressure,
                'wind_speed': weather_cache.wind_speed,
                'wind_direction': weather_cache.wind_direction,
                'conditions': weather_cache.conditions,
                'icon': weather_cache.icon,
                'forecast': weather_cache.forecast,
                'cached': True
            }
            cache.set(cache_key, data, timeout=300)  # Cache for 5 minutes
            return JsonResponse(data)
    except WeatherCache.DoesNotExist:
        pass
    
    # Fetch from API
    client = OpenWeatherClient()
    data = client.get_weather(location)
    
    if data:
        # Save to cache
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
        
        cache.set(cache_key, data, timeout=300)
        return JsonResponse(data)
    
    return JsonResponse({'error': 'Unable to fetch weather data'}, status=503)


def get_fuel_prices(request, location):
    """Get fuel prices for location"""
    cache_key = f"fuel_{location}"
    cached = cache.get(cache_key)
    if cached:
        return JsonResponse(cached)
    
    try:
        fuel_cache = FuelPriceCache.objects.get(location_code=location)
        if not fuel_cache.is_expired():
            data = {
                'location': location,
                'jet_a': float(fuel_cache.jet_a_price),
                'avgas': float(fuel_cache.avgas_price),
                'currency': fuel_cache.currency,
                'cached': True
            }
            cache.set(cache_key, data, timeout=300)
            return JsonResponse(data)
    except FuelPriceCache.DoesNotExist:
        pass
    
    # Fetch from API (placeholder)
    data = {
        'location': location,
        'jet_a': 5.50,
        'avgas': 6.25,
        'currency': 'USD',
        'cached': False
    }
    
    # Save to cache
    FuelPriceCache.objects.update_or_create(
        location_code=location,
        defaults={
            'jet_a_price': data['jet_a'],
            'avgas_price': data['avgas'],
            'expires_at': timezone.now() + timezone.timedelta(days=1)
        }
    )
    
    cache.set(cache_key, data, timeout=3600)
    return JsonResponse(data)


def get_exchange_rate(request, from_currency, to_currency):
    """Get exchange rate between currencies"""
    cache_key = f"exchange_{from_currency}_{to_currency}"
    cached = cache.get(cache_key)
    if cached:
        return JsonResponse(cached)
    
    try:
        rate_cache = ExchangeRateCache.objects.get(
            from_currency=from_currency,
            to_currency=to_currency
        )
        if not rate_cache.is_expired():
            data = {
                'from': from_currency,
                'to': to_currency,
                'rate': float(rate_cache.rate),
                'cached': True
            }
            cache.set(cache_key, data, timeout=300)
            return JsonResponse(data)
    except ExchangeRateCache.DoesNotExist:
        pass
    
    # Fetch from API
    client = ForexClient()
    rate = client.get_rate(from_currency, to_currency)
    
    if rate:
        data = {
            'from': from_currency,
            'to': to_currency,
            'rate': rate,
            'cached': False
        }
        
        # Save to cache
        ExchangeRateCache.objects.update_or_create(
            from_currency=from_currency,
            to_currency=to_currency,
            defaults={
                'rate': rate,
                'expires_at': timezone.now() + timezone.timedelta(hours=1)
            }
        )
        
        cache.set(cache_key, data, timeout=300)
        return JsonResponse(data)
    
    return JsonResponse({'error': 'Unable to fetch exchange rate'}, status=503)