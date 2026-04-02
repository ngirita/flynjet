import requests
from django.conf import settings
from django.core.cache import cache
from .models import WeatherCache
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class WeatherService:
    """Comprehensive weather service with multiple providers"""
    
    PROVIDERS = {
        'openweather': {
            'url': 'https://api.openweathermap.org/data/2.5/weather',
            'api_key': settings.OPENWEATHER_API_KEY,
            'enabled': bool(settings.OPENWEATHER_API_KEY)
        },
        'aviationweather': {
            'url': 'https://aviationweather.gov/api/data/metar',
            'enabled': True
        },
        'weatherbit': {
            'url': 'https://api.weatherbit.io/v2.0/current',
            'api_key': settings.WEATHERBIT_API_KEY,
            'enabled': bool(settings.WEATHERBIT_API_KEY)
        }
    }
    
    @classmethod
    def get_weather(cls, location, provider='openweather'):
        """Get weather data for location"""
        # Check cache first
        cache_key = f"weather_{location}"
        cached = cache.get(cache_key)
        if cached:
            return cached
        
        # Check database cache
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
                    'source': 'cache'
                }
                cache.set(cache_key, data, timeout=300)
                return data
        except WeatherCache.DoesNotExist:
            pass
        
        # Fetch from provider
        if provider == 'openweather':
            data = cls._get_openweather(location)
        elif provider == 'aviationweather':
            data = cls._get_aviationweather(location)
        elif provider == 'weatherbit':
            data = cls._get_weatherbit(location)
        else:
            data = None
        
        if data:
            # Save to cache
            cls._cache_weather(location, data)
            cache.set(cache_key, data, timeout=300)
        
        return data
    
    @classmethod
    def _get_openweather(cls, location):
        """Get weather from OpenWeatherMap"""
        if not cls.PROVIDERS['openweather']['enabled']:
            logger.warning("OpenWeather API key not configured")
            return None
        
        try:
            params = {
                'q': location,
                'appid': cls.PROVIDERS['openweather']['api_key'],
                'units': 'metric'
            }
            
            response = requests.get(
                cls.PROVIDERS['openweather']['url'],
                params=params,
                timeout=10
            )
            response.raise_for_status()
            
            data = response.json()
            
            return {
                'temperature': data['main']['temp'],
                'feels_like': data['main']['feels_like'],
                'humidity': data['main']['humidity'],
                'pressure': data['main']['pressure'],
                'wind_speed': data['wind']['speed'],
                'wind_direction': data['wind']['deg'],
                'conditions': data['weather'][0]['description'],
                'icon': data['weather'][0]['icon'],
                'source': 'openweather'
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"OpenWeather API error: {e}")
            return None
    
    @classmethod
    def _get_aviationweather(cls, location):
        """Get weather from AviationWeather.gov (METAR)"""
        try:
            params = {
                'ids': location,
                'format': 'json'
            }
            
            response = requests.get(
                cls.PROVIDERS['aviationweather']['url'],
                params=params,
                timeout=10
            )
            response.raise_for_status()
            
            data = response.json()
            
            if data and len(data) > 0:
                metar = data[0]
                return {
                    'temperature': metar.get('temp', 0),
                    'dewpoint': metar.get('dewpoint', 0),
                    'wind_speed': metar.get('wspd', 0),
                    'wind_direction': metar.get('wdir', 0),
                    'visibility': metar.get('visib', 0),
                    'conditions': metar.get('flight_category', 'UNKNOWN'),
                    'raw': metar.get('raw', ''),
                    'source': 'aviationweather'
                }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"AviationWeather API error: {e}")
        
        return None
    
    @classmethod
    def _get_weatherbit(cls, location):
        """Get weather from Weatherbit.io"""
        if not cls.PROVIDERS['weatherbit']['enabled']:
            return None
        
        try:
            params = {
                'city': location,
                'key': cls.PROVIDERS['weatherbit']['api_key'],
                'units': 'M'
            }
            
            response = requests.get(
                cls.PROVIDERS['weatherbit']['url'],
                params=params,
                timeout=10
            )
            response.raise_for_status()
            
            data = response.json()
            
            if data.get('data') and len(data['data']) > 0:
                weather = data['data'][0]
                return {
                    'temperature': weather['temp'],
                    'feels_like': weather['app_temp'],
                    'humidity': weather['rh'],
                    'pressure': weather['pres'],
                    'wind_speed': weather['wind_spd'],
                    'wind_direction': weather['wind_dir'],
                    'conditions': weather['weather']['description'],
                    'icon': weather['weather']['icon'],
                    'source': 'weatherbit'
                }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Weatherbit API error: {e}")
        
        return None
    
    @classmethod
    def _cache_weather(cls, location, data):
        """Cache weather data in database"""
        WeatherCache.objects.update_or_create(
            location_key=location,
            defaults={
                'temperature': data.get('temperature', 0),
                'feels_like': data.get('feels_like', 0),
                'humidity': data.get('humidity', 0),
                'pressure': data.get('pressure', 0),
                'wind_speed': data.get('wind_speed', 0),
                'wind_direction': data.get('wind_direction', 0),
                'conditions': data.get('conditions', 'Unknown'),
                'icon': data.get('icon', ''),
                'expires_at': datetime.now() + timedelta(hours=1)
            }
        )
    
    @classmethod
    def get_forecast(cls, location, days=5):
        """Get weather forecast"""
        # Implement forecast logic here
        pass
    
    @classmethod
    def get_metar(cls, airport_code):
        """Get METAR for airport"""
        return cls._get_aviationweather(airport_code)
    
    @classmethod
    def get_taf(cls, airport_code):
        """Get TAF (Terminal Aerodrome Forecast)"""
        try:
            params = {
                'ids': airport_code,
                'format': 'json',
                'taf': 'true'
            }
            
            response = requests.get(
                cls.PROVIDERS['aviationweather']['url'],
                params=params,
                timeout=10
            )
            response.raise_for_status()
            
            data = response.json()
            
            if data and len(data) > 0:
                return data[0].get('taf', '')
            
        except requests.exceptions.RequestException as e:
            logger.error(f"TAF API error: {e}")
        
        return None


class WeatherAlert:
    """Weather alerts and warnings"""
    
    SEVERE_CONDITIONS = {
        'thunderstorm': ['thunderstorm', 'ts', 'tstorm'],
        'tornado': ['tornado', 'tor'],
        'hurricane': ['hurricane', 'hur'],
        'blizzard': ['blizzard', 'blz'],
        'ice': ['ice', 'fz', 'freezing'],
        'fog': ['fog', 'fg', 'mist']
    }
    
    @classmethod
    def check_severe_weather(cls, conditions):
        """Check if conditions indicate severe weather"""
        conditions_lower = conditions.lower()
        
        for severity, keywords in cls.SEVERE_CONDITIONS.items():
            for keyword in keywords:
                if keyword in conditions_lower:
                    return {
                        'alert': True,
                        'severity': severity,
                        'message': f"Severe weather detected: {severity}"
                    }
        
        return {'alert': False}
    
    @classmethod
    def get_wind_alert(cls, wind_speed):
        """Get wind-related alerts"""
        if wind_speed > 50:
            return {
                'alert': True,
                'severity': 'high',
                'message': f"High winds: {wind_speed} knots"
            }
        elif wind_speed > 30:
            return {
                'alert': True,
                'severity': 'moderate',
                'message': f"Strong winds: {wind_speed} knots"
            }
        return {'alert': False}
    
    @classmethod
    def get_visibility_alert(cls, visibility):
        """Get visibility-related alerts"""
        if visibility < 1:
            return {
                'alert': True,
                'severity': 'high',
                'message': f"Very low visibility: {visibility} miles"
            }
        elif visibility < 3:
            return {
                'alert': True,
                'severity': 'moderate',
                'message': f"Reduced visibility: {visibility} miles"
            }
        return {'alert': False}