import requests
from django.conf import settings
from django.core.cache import cache
from .models import FuelPriceCache
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class FuelPriceService:
    """Aviation fuel price service"""
    
    PROVIDERS = {
        'iata': {
            'url': 'https://www.iata.org/fuel-price-monitor',
            'enabled': True
        },
        'airnav': {
            'url': 'https://www.airnav.com/fuel/local.html',
            'enabled': True
        },
        'fuel_api': {
            'url': getattr(settings, 'FUEL_API_URL', ''),
            'api_key': getattr(settings, 'FUEL_API_KEY', ''),
            'enabled': bool(getattr(settings, 'FUEL_API_KEY', ''))
        }
    }
    
    FUEL_TYPES = {
        'jet_a': 'Jet A',
        'jet_a1': 'Jet A-1',
        'avgas_100ll': 'Avgas 100LL',
        'avgas_100': 'Avgas 100'
    }
    
    @classmethod
    def get_fuel_price(cls, location_code, fuel_type='jet_a'):
        """Get fuel price for location"""
        cache_key = f"fuel_{location_code}_{fuel_type}"
        cached = cache.get(cache_key)
        if cached:
            return cached
        
        # Check database cache
        try:
            fuel_cache = FuelPriceCache.objects.get(
                location_code=location_code
            )
            if not fuel_cache.is_expired():
                price = getattr(fuel_cache, f"{fuel_type}_price", None)
                if price:
                    data = {
                        'location': location_code,
                        'fuel_type': fuel_type,
                        'price': float(price),
                        'currency': fuel_cache.currency,
                        'source': 'cache'
                    }
                    cache.set(cache_key, data, timeout=300)
                    return data
        except FuelPriceCache.DoesNotExist:
            pass
        
        # Fetch from providers
        data = None
        for provider_name, provider in cls.PROVIDERS.items():
            if provider['enabled']:
                data = cls._fetch_from_provider(provider_name, location_code, fuel_type)
                if data:
                    break
        
        if data:
            cls._cache_price(location_code, fuel_type, data)
            cache.set(cache_key, data, timeout=3600)
        
        return data
    
    @classmethod
    def _fetch_from_provider(cls, provider, location_code, fuel_type):
        """Fetch price from specific provider"""
        if provider == 'fuel_api' and cls.PROVIDERS['fuel_api']['enabled']:
            return cls._get_fuel_api(location_code, fuel_type)
        elif provider == 'airnav':
            return cls._scrape_airnav(location_code)
        elif provider == 'iata':
            return cls._get_iata_data(location_code)
        
        return None
    
    @classmethod
    def _get_fuel_api(cls, location_code, fuel_type):
        """Get price from fuel API"""
        try:
            params = {
                'location': location_code,
                'fuel_type': fuel_type,
                'api_key': cls.PROVIDERS['fuel_api']['api_key']
            }
            
            response = requests.get(
                cls.PROVIDERS['fuel_api']['url'],
                params=params,
                timeout=10
            )
            response.raise_for_status()
            
            data = response.json()
            
            return {
                'price': data.get('price', 0),
                'currency': data.get('currency', 'USD'),
                'last_updated': data.get('timestamp'),
                'source': 'fuel_api'
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Fuel API error: {e}")
            return None
    
    @classmethod
    def _scrape_airnav(cls, location_code):
        """Scrape price from AirNav"""
        try:
            params = {'id': location_code}
            
            response = requests.get(
                cls.PROVIDERS['airnav']['url'],
                params=params,
                timeout=10
            )
            
            if response.status_code == 200:
                return cls._parse_airnav_response(response.text, location_code)
            
        except requests.exceptions.RequestException as e:
            logger.error(f"AirNav scraping error: {e}")
        
        return None
    
    @classmethod
    def _parse_airnav_response(cls, html, location_code):
        """Parse AirNav HTML response"""
        import re
        
        # Extract fuel prices using regex
        jet_a_pattern = r'Jet A[^\d]*(\d+\.\d+)'
        avgas_pattern = r'100LL[^\d]*(\d+\.\d+)'
        
        jet_a_match = re.search(jet_a_pattern, html)
        avgas_match = re.search(avgas_pattern, html)
        
        return {
            'jet_a': float(jet_a_match.group(1)) if jet_a_match else None,
            'avgas': float(avgas_match.group(1)) if avgas_match else None,
            'currency': 'USD',
            'source': 'airnav'
        }
    
    @classmethod
    def _get_iata_data(cls, location_code):
        """Get data from IATA fuel monitor"""
        # IATA data would require subscription
        # This is a placeholder
        return None
    
    @classmethod
    def _cache_price(cls, location_code, fuel_type, data):
        """Cache price in database"""
        defaults = {
            f"{fuel_type}_price": data.get('price', data.get(fuel_type, 0)),
            'currency': data.get('currency', 'USD'),
            'expires_at': datetime.now() + timedelta(days=1)
        }
        
        FuelPriceCache.objects.update_or_create(
            location_code=location_code,
            defaults=defaults
        )
    
    @classmethod
    def get_price_trend(cls, location_code, days=30):
        """Get price trend for location"""
        # This would need historical data
        # Placeholder implementation
        return {
            'current': 5.50,
            'average': 5.45,
            'min': 5.20,
            'max': 5.80,
            'trend': 'stable'
        }
    
    @classmethod
    def compare_prices(cls, location_codes):
        """Compare prices across locations"""
        comparison = {}
        
        for code in location_codes:
            price_data = cls.get_fuel_price(code)
            if price_data:
                comparison[code] = price_data
        
        return comparison
    
    @classmethod
    def get_nearest_airports(cls, latitude, longitude, radius_km=100):
        """Get nearest airports with fuel prices"""
        # This would need airport database
        # Placeholder
        return []


class FuelPlanner:
    """Fuel planning and optimization"""
    
    @staticmethod
    def calculate_fuel_requirements(aircraft, distance, reserves_hours=1):
        """Calculate fuel requirements for flight"""
        # Fuel consumption calculation
        fuel_per_hour = aircraft.fuel_consumption_lph
        flight_hours = distance / aircraft.cruise_speed_knots
        
        trip_fuel = fuel_per_hour * flight_hours
        reserve_fuel = fuel_per_hour * reserves_hours
        
        return {
            'trip_fuel': trip_fuel,
            'reserve_fuel': reserve_fuel,
            'total_fuel': trip_fuel + reserve_fuel,
            'fuel_per_hour': fuel_per_hour,
            'flight_hours': flight_hours
        }
    
    @staticmethod
    def find_cheapest_fuel_stops(route, aircraft_range):
        """Find cheapest fuel stops along route"""
        # This would need route planning algorithm
        # Placeholder
        return []
    
    @staticmethod
    def calculate_fuel_cost(price_per_gallon, gallons):
        """Calculate fuel cost"""
        return price_per_gallon * gallons