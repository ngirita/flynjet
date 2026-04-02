# apps/payments/exchange_utils.py - FIXED VERSION

import requests
from decimal import Decimal
from django.core.cache import cache
import logging

logger = logging.getLogger(__name__)

class CurrencyExchangeService:
    """
    Real-time currency exchange service with multiple API fallbacks
    """
    
    def __init__(self):
        # Use multiple free APIs for reliability
        self.fallback_rate = Decimal('130.0')  # 1 USD = 130 KES (fallback)
        
    def get_exchange_rate(self, from_currency, to_currency):
        """
        Get exchange rate from one currency to another
        Example: get_exchange_rate('USD', 'KES') -> 130.50
        """
        cache_key = f'exchange_rate_{from_currency}_{to_currency}'
        cached_rate = cache.get(cache_key)
        
        if cached_rate:
            return Decimal(str(cached_rate))
        
        # Try multiple API endpoints
        apis = [
            f"https://api.exchangerate-api.com/v4/latest/{from_currency}",
            f"https://api.frankfurter.dev/v1/latest?base={from_currency}",
            f"https://api.exchangerate.host/latest?base={from_currency}",
        ]
        
        for api_url in apis:
            try:
                response = requests.get(api_url, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    # Handle different API response formats
                    if 'rates' in data:
                        rate = data['rates'].get(to_currency)
                    elif 'data' in data and 'rates' in data['data']:
                        rate = data['data']['rates'].get(to_currency)
                    else:
                        continue
                        
                    if rate:
                        rate = Decimal(str(rate))
                        cache.set(cache_key, float(rate), 3600)  # Cache for 1 hour
                        logger.info(f"Exchange rate from API: 1 {from_currency} = {rate} {to_currency}")
                        return rate
            except Exception as e:
                logger.warning(f"API {api_url} failed: {e}")
                continue
        
        # If all APIs fail, return fallback rate
        logger.warning(f"Using fallback rate: 1 {from_currency} = {self.fallback_rate} {to_currency}")
        return self.fallback_rate
    
    def convert_currency(self, amount, from_currency, to_currency):
        """Convert amount from one currency to another"""
        if from_currency == to_currency:
            return amount
        rate = self.get_exchange_rate(from_currency, to_currency)
        return amount * rate
    
    def convert_usd_to_kes(self, usd_amount):
        """Convert USD to KES"""
        return self.convert_currency(usd_amount, 'USD', 'KES')
    
    def get_supported_currencies(self):
        """Get list of supported currencies"""
        return ['USD', 'EUR', 'GBP', 'KES', 'JPY', 'CAD', 'AUD', 'CHF', 'CNY', 'NGN']