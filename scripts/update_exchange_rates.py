#!/usr/bin/env python
import os
import sys
import django
import requests
from datetime import datetime, timedelta

# Setup Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'flynjet.settings')
django.setup()

from apps.integrations.models import ExchangeRateCache
from django.conf import settings
from django.utils import timezone
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def update_exchange_rates():
    """Update exchange rates from external API"""
    base_currency = 'USD'
    target_currencies = ['EUR', 'GBP', 'JPY', 'AED', 'CAD', 'AUD', 'CHF', 'CNY']
    
    # Try multiple APIs
    rates = None
    
    # Try OpenExchangeRates
    if settings.OPENEXCHANGE_API_KEY:
        try:
            response = requests.get(
                f"https://openexchangerates.org/api/latest.json",
                params={
                    'app_id': settings.OPENEXCHANGE_API_KEY,
                    'base': base_currency
                },
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                rates = data.get('rates')
                logger.info("Fetched rates from OpenExchangeRates")
        except Exception as e:
            logger.error(f"OpenExchangeRates error: {e}")
    
    # Try Fixer.io as backup
    if not rates and settings.FIXER_API_KEY:
        try:
            response = requests.get(
                f"http://data.fixer.io/api/latest",
                params={
                    'access_key': settings.FIXER_API_KEY,
                    'base': base_currency,
                    'symbols': ','.join(target_currencies)
                },
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    rates = data.get('rates')
                    logger.info("Fetched rates from Fixer.io")
        except Exception as e:
            logger.error(f"Fixer.io error: {e}")
    
    # Try free API as last resort
    if not rates:
        try:
            response = requests.get(
                f"https://api.exchangerate-api.com/v4/latest/{base_currency}",
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                rates = data.get('rates')
                logger.info("Fetched rates from ExchangeRate-API")
        except Exception as e:
            logger.error(f"ExchangeRate-API error: {e}")
    
    if rates:
        updated = 0
        expiry = timezone.now() + timedelta(hours=1)
        
        for currency in target_currencies:
            if currency in rates:
                ExchangeRateCache.objects.update_or_create(
                    from_currency=base_currency,
                    to_currency=currency,
                    defaults={
                        'rate': rates[currency],
                        'expires_at': expiry
                    }
                )
                updated += 1
                logger.info(f"Updated {base_currency} → {currency}: {rates[currency]}")
        
        logger.info(f"Updated {updated} exchange rates")
        return updated
    
    logger.error("Failed to fetch exchange rates")
    return 0

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Update exchange rates')
    parser.add_argument('--force', action='store_true', help='Force update even if not expired')
    
    args = parser.parse_args()
    
    if args.force:
        # Clear cache
        ExchangeRateCache.objects.all().delete()
        logger.info("Cleared existing rates")
    
    updated = update_exchange_rates()
    
    if updated > 0:
        logger.info(f"Successfully updated {updated} rates")
    else:
        logger.error("Failed to update rates")
        sys.exit(1)

if __name__ == '__main__':
    main()