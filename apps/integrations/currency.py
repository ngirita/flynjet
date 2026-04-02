import requests
from django.conf import settings
from django.core.cache import cache
from .models import ExchangeRateCache
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class CurrencyService:
    """Currency exchange rate service"""
    
    PROVIDERS = {
        'openexchange': {
            'url': 'https://openexchangerates.org/api/latest.json',
            'api_key': settings.OPENEXCHANGE_API_KEY,
            'enabled': bool(settings.OPENEXCHANGE_API_KEY)
        },
        'fixer': {
            'url': 'http://data.fixer.io/api/latest',
            'api_key': settings.FIXER_API_KEY,
            'enabled': bool(settings.FIXER_API_KEY)
        },
        'exchangerate': {
            'url': 'https://api.exchangerate-api.com/v4/latest',
            'enabled': True
        }
    }
    
    SUPPORTED_CURRENCIES = [
        'USD', 'EUR', 'GBP', 'JPY', 'AED', 'CAD', 'AUD', 'CHF',
        'CNY', 'HKD', 'SGD', 'INR', 'BRL', 'ZAR', 'RUB', 'KRW'
    ]
    
    @classmethod
    def get_rate(cls, from_currency, to_currency):
        """Get exchange rate between currencies"""
        cache_key = f"exchange_{from_currency}_{to_currency}"
        cached = cache.get(cache_key)
        if cached:
            return cached
        
        # Check database cache
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
                    'source': 'cache'
                }
                cache.set(cache_key, data, timeout=300)
                return data
        except ExchangeRateCache.DoesNotExist:
            pass
        
        # Fetch from providers
        data = None
        for provider_name, provider in cls.PROVIDERS.items():
            if provider['enabled']:
                data = cls._fetch_rate(provider_name, from_currency, to_currency)
                if data:
                    break
        
        if data:
            cls._cache_rate(from_currency, to_currency, data)
            cache.set(cache_key, data, timeout=3600)
        
        return data
    
    @classmethod
    def _fetch_rate(cls, provider, from_currency, to_currency):
        """Fetch rate from specific provider"""
        if provider == 'openexchange':
            return cls._get_openexchange(from_currency, to_currency)
        elif provider == 'fixer':
            return cls._get_fixer(from_currency, to_currency)
        elif provider == 'exchangerate':
            return cls._get_exchangerate(from_currency, to_currency)
        
        return None
    
    @classmethod
    def _get_openexchange(cls, from_currency, to_currency):
        """Get rate from OpenExchangeRates"""
        try:
            params = {
                'app_id': cls.PROVIDERS['openexchange']['api_key'],
                'base': from_currency
            }
            
            response = requests.get(
                cls.PROVIDERS['openexchange']['url'],
                params=params,
                timeout=10
            )
            response.raise_for_status()
            
            data = response.json()
            
            if to_currency in data.get('rates', {}):
                return {
                    'rate': data['rates'][to_currency],
                    'timestamp': data['timestamp'],
                    'source': 'openexchange'
                }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"OpenExchange API error: {e}")
        
        return None
    
    @classmethod
    def _get_fixer(cls, from_currency, to_currency):
        """Get rate from Fixer.io"""
        try:
            params = {
                'access_key': cls.PROVIDERS['fixer']['api_key'],
                'base': from_currency,
                'symbols': to_currency
            }
            
            response = requests.get(
                cls.PROVIDERS['fixer']['url'],
                params=params,
                timeout=10
            )
            response.raise_for_status()
            
            data = response.json()
            
            if data.get('success'):
                return {
                    'rate': data['rates'][to_currency],
                    'timestamp': data['timestamp'],
                    'source': 'fixer'
                }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Fixer API error: {e}")
        
        return None
    
    @classmethod
    def _get_exchangerate(cls, from_currency, to_currency):
        """Get rate from ExchangeRate-API"""
        try:
            response = requests.get(
                f"{cls.PROVIDERS['exchangerate']['url']}/{from_currency}",
                timeout=10
            )
            response.raise_for_status()
            
            data = response.json()
            
            if to_currency in data.get('rates', {}):
                return {
                    'rate': data['rates'][to_currency],
                    'timestamp': datetime.now().timestamp(),
                    'source': 'exchangerate'
                }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"ExchangeRate API error: {e}")
        
        return None
    
    @classmethod
    def _cache_rate(cls, from_currency, to_currency, data):
        """Cache rate in database"""
        ExchangeRateCache.objects.update_or_create(
            from_currency=from_currency,
            to_currency=to_currency,
            defaults={
                'rate': data['rate'],
                'expires_at': datetime.now() + timedelta(hours=1)
            }
        )
    
    @classmethod
    def convert(cls, amount, from_currency, to_currency):
        """Convert amount between currencies"""
        rate_data = cls.get_rate(from_currency, to_currency)
        if rate_data:
            converted = amount * rate_data['rate']
            return {
                'original_amount': amount,
                'from_currency': from_currency,
                'to_currency': to_currency,
                'converted_amount': converted,
                'rate': rate_data['rate'],
                'source': rate_data['source']
            }
        return None
    
    @classmethod
    def get_all_rates(cls, base_currency='USD'):
        """Get all exchange rates for base currency"""
        cache_key = f"all_rates_{base_currency}"
        cached = cache.get(cache_key)
        if cached:
            return cached
        
        # Try to get from provider
        for provider_name, provider in cls.PROVIDERS.items():
            if provider['enabled']:
                data = cls._fetch_all_rates(provider_name, base_currency)
                if data:
                    cache.set(cache_key, data, timeout=3600)
                    return data
        
        return {}
    
    @classmethod
    def _fetch_all_rates(cls, provider, base_currency):
        """Fetch all rates from provider"""
        if provider == 'exchangerate':
            try:
                response = requests.get(
                    f"{cls.PROVIDERS['exchangerate']['url']}/{base_currency}",
                    timeout=10
                )
                response.raise_for_status()
                
                data = response.json()
                return data.get('rates', {})
                
            except requests.exceptions.RequestException as e:
                logger.error(f"ExchangeRate API error: {e}")
        
        return None
    
    @classmethod
    def get_historical_rate(cls, from_currency, to_currency, date):
        """Get historical exchange rate"""
        # Would need historical data API
        # Placeholder
        return None


class CurrencyFormatter:
    """Format currency values"""
    
    CURRENCY_SYMBOLS = {
        'USD': '$',
        'EUR': '€',
        'GBP': '£',
        'JPY': '¥',
        'AED': 'د.إ',
        'CAD': 'C$',
        'AUD': 'A$',
        'CHF': 'Fr',
        'CNY': '¥',
        'HKD': 'HK$',
        'SGD': 'S$',
        'INR': '₹',
        'BRL': 'R$',
        'ZAR': 'R',
        'RUB': '₽',
        'KRW': '₩'
    }
    
    @classmethod
    def format(cls, amount, currency='USD', include_symbol=True):
        """Format currency amount"""
        if include_symbol:
            symbol = cls.CURRENCY_SYMBOLS.get(currency, '$')
            return f"{symbol}{amount:,.2f}"
        else:
            return f"{amount:,.2f} {currency}"
    
    @classmethod
    def get_symbol(cls, currency):
        """Get currency symbol"""
        return cls.CURRENCY_SYMBOLS.get(currency, '$')