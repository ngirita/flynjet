import requests
from django.conf import settings
from django.core.cache import cache
import logging

logger = logging.getLogger(__name__)

class ForexClient:
    """Client for foreign exchange rates"""
    
    BASE_URL = "https://api.exchangerate-api.com/v4/latest"
    
    def __init__(self):
        self.api_key = settings.EXCHANGERATE_API_KEY
        self.session = requests.Session()
    
    def get_rate(self, from_currency, to_currency):
        """Get exchange rate between currencies"""
        # Check cache first
        cache_key = f"forex_rate_{from_currency}_{to_currency}"
        cached_rate = cache.get(cache_key)
        if cached_rate:
            return cached_rate
        
        try:
            # Use free API if no key configured
            if not self.api_key:
                url = f"https://api.exchangerate-api.com/v4/latest/{from_currency}"
            else:
                url = f"{self.BASE_URL}/{from_currency}"
                params = {'access_key': self.api_key}
            
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if 'rates' in data and to_currency in data['rates']:
                rate = data['rates'][to_currency]
                # Cache for 1 hour
                cache.set(cache_key, rate, timeout=3600)
                return rate
            
            logger.error(f"Currency {to_currency} not found in rates")
            return None
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching exchange rate: {e}")
            return None
    
    def convert(self, amount, from_currency, to_currency):
        """Convert amount between currencies"""
        rate = self.get_rate(from_currency, to_currency)
        if rate:
            return amount * rate
        return None
    
    def get_all_rates(self, base_currency='USD'):
        """Get all exchange rates for base currency"""
        try:
            if not self.api_key:
                url = f"https://api.exchangerate-api.com/v4/latest/{base_currency}"
            else:
                url = f"{self.BASE_URL}/{base_currency}"
                params = {'access_key': self.api_key}
            
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            return data.get('rates', {})
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching all rates: {e}")
            return {}