from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.core.cache import cache
from .models import WeatherCache, FuelPriceCache, ExchangeRateCache
import logging

logger = logging.getLogger(__name__)

@receiver(post_save, sender=WeatherCache)
def invalidate_weather_cache(sender, instance, **kwargs):
    """Invalidate weather cache when new data is saved"""
    cache_key = f"weather_{instance.location_key}"
    cache.delete(cache_key)
    logger.info(f"Invalidated weather cache for {instance.location_key}")

@receiver(post_save, sender=FuelPriceCache)
def invalidate_fuel_cache(sender, instance, **kwargs):
    """Invalidate fuel price cache when new data is saved"""
    cache_key = f"fuel_{instance.location_code}"
    cache.delete(cache_key)
    logger.info(f"Invalidated fuel cache for {instance.location_code}")

@receiver(post_save, sender=ExchangeRateCache)
def invalidate_exchange_cache(sender, instance, **kwargs):
    """Invalidate exchange rate cache when new data is saved"""
    cache_key = f"exchange_{instance.from_currency}_{instance.to_currency}"
    cache.delete(cache_key)
    logger.info(f"Invalidated exchange cache for {instance.from_currency}/{instance.to_currency}")

@receiver(pre_save, sender=WeatherCache)
def check_weather_thresholds(sender, instance, **kwargs):
    """Check for extreme weather conditions"""
    if instance.temperature > 40 or instance.temperature < -20:
        logger.warning(f"Extreme temperature at {instance.location_key}: {instance.temperature}°C")
        # Could send alerts here

@receiver(pre_save, sender=FuelPriceCache)
def check_fuel_price_spikes(sender, instance, **kwargs):
    """Check for significant fuel price changes"""
    try:
        old = FuelPriceCache.objects.get(location_code=instance.location_code)
        if old.jet_a_price:
            change_pct = abs((instance.jet_a_price - old.jet_a_price) / old.jet_a_price * 100)
            if change_pct > 20:
                logger.warning(f"Significant fuel price change at {instance.location_code}: {change_pct:.1f}%")
    except FuelPriceCache.DoesNotExist:
        pass