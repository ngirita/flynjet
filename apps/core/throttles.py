from rest_framework.throttling import UserRateThrottle, AnonRateThrottle, ScopedRateThrottle
from django.core.cache import cache
import time

class BurstRateThrottle(UserRateThrottle):
    """
    Limits burst rate - for sudden spikes in traffic.
    Allows 60 requests per minute.
    """
    rate = '60/minute'
    scope = 'burst'


class SustainedRateThrottle(UserRateThrottle):
    """
    Limits sustained rate - for long-term usage.
    Allows 1000 requests per hour.
    """
    rate = '1000/hour'
    scope = 'sustained'


class BookingCreateThrottle(UserRateThrottle):
    """
    Specifically limits booking creation to prevent spam.
    Allows 10 booking creations per hour per user.
    """
    rate = '10/hour'
    scope = 'booking_create'


class PaymentProcessThrottle(UserRateThrottle):
    """
    Limits payment attempts to prevent brute force.
    Allows 20 payment attempts per hour per user.
    """
    rate = '20/hour'
    scope = 'payment_process'


class LoginRateThrottle(AnonRateThrottle):
    """
    Limits login attempts for anonymous users.
    Allows 5 attempts per minute.
    """
    rate = '5/minute'
    scope = 'login'


class RegistrationRateThrottle(AnonRateThrottle):
    """
    Limits registration attempts to prevent spam accounts.
    Allows 3 registrations per hour per IP.
    """
    rate = '3/hour'
    scope = 'registration'


class PasswordResetThrottle(AnonRateThrottle):
    """
    Limits password reset requests.
    Allows 3 requests per hour per email.
    """
    rate = '3/hour'
    scope = 'password_reset'


class APIAccessThrottle(UserRateThrottle):
    """
    Limits general API access.
    Different rates for different user types.
    """
    scope = 'api_access'
    
    def get_rate(self):
        if getattr(self.request.user, 'user_type', None) == 'admin':
            return '10000/hour'
        elif getattr(self.request.user, 'user_type', None) == 'agent':
            return '5000/hour'
        return '1000/hour'


class IPBasedThrottle(AnonRateThrottle):
    """
    Rate limiting based on IP address for anonymous users.
    """
    scope = 'ip_based'
    rate = '100/hour'
    
    def get_cache_key(self, request, view):
        # Use IP address as cache key
        ident = self.get_ident(request)
        return self.cache_format % {
            'scope': self.scope,
            'ident': ident
        }


class ScopedUserRateThrottle(ScopedRateThrottle):
    """
    Allows different rate limits for different views/scopes.
    """
    def allow_request(self, request, view):
        # We can add custom logic here
        return super().allow_request(request, view)


class DynamicRateThrottle(UserRateThrottle):
    """
    Dynamic rate limiting based on user subscription level.
    """
    scope = 'dynamic'
    
    def get_rate(self):
        if not self.request.user.is_authenticated:
            return '20/hour'
        
        # Different rates based on user type
        user_type = self.request.user.user_type
        if user_type == 'premium':
            return '5000/hour'
        elif user_type == 'corporate':
            return '3000/hour'
        elif user_type == 'regular':
            return '1000/hour'
        else:
            return '100/hour'
    
    def get_cache_key(self, request, view):
        if request.user.is_authenticated:
            ident = request.user.pk
        else:
            ident = self.get_ident(request)
        
        return self.cache_format % {
            'scope': self.scope,
            'ident': ident
        }


class ConcurrentRequestThrottle:
    """
    Limits concurrent requests per user.
    Not a DRF throttle, but custom middleware-based limiting.
    """
    def __init__(self, max_concurrent=5):
        self.max_concurrent = max_concurrent
    
    def allow_request(self, user_id):
        """Check if user has too many concurrent requests."""
        key = f"concurrent_requests_{user_id}"
        current = cache.get(key, 0)
        
        if current >= self.max_concurrent:
            return False
        
        # Increment counter
        cache.set(key, current + 1, timeout=30)  # 30 second timeout
        return True
    
    def release_request(self, user_id):
        """Release a request slot."""
        key = f"concurrent_requests_{user_id}"
        current = cache.get(key, 0)
        if current > 0:
            cache.set(key, current - 1, timeout=30)


class EndpointSpecificThrottle(UserRateThrottle):
    """
    Different limits for different endpoints.
    """
    def __init__(self):
        self.endpoint_limits = {
            'search': '100/minute',
            'details': '200/minute',
            'book': '10/minute',
            'pay': '5/minute',
        }
        super().__init__()
    
    def get_rate(self):
        # Get endpoint name from view
        view = getattr(self, 'view', None)
        if view and hasattr(view, 'endpoint_type'):
            endpoint = view.endpoint_type
            return self.endpoint_limits.get(endpoint, '60/minute')
        return '60/minute'


class TimeBasedThrottle(UserRateThrottle):
    """
    Different limits based on time of day.
    """
    scope = 'time_based'
    
    def get_rate(self):
        hour = time.localtime().tm_hour
        
        # Stricter limits during peak hours (9 AM - 5 PM)
        if 9 <= hour <= 17:
            return '500/hour'  # Peak hours
        else:
            return '1000/hour'  # Off-peak


class UserActivityThrottle(UserRateThrottle):
    """
    Adjusts limits based on user activity level.
    """
    scope = 'user_activity'
    
    def get_rate(self):
        if not self.request.user.is_authenticated:
            return '50/hour'
        
        # Get user's booking history count
        booking_count = self.request.user.bookings.count()
        
        # Trusted users with history get higher limits
        if booking_count > 50:
            return '2000/hour'
        elif booking_count > 20:
            return '1500/hour'
        elif booking_count > 5:
            return '1000/hour'
        else:
            return '500/hour'


class MaintenanceModeThrottle:
    """
    Special throttle for maintenance mode - only allows staff.
    """
    def allow_request(self, request, view):
        if getattr(request, 'maintenance_mode', False):
            # During maintenance, only allow staff
            return request.user.is_staff
        return True


class GeographicThrottle(AnonRateThrottle):
    """
    Different limits based on geographic location.
    """
    scope = 'geographic'
    
    def get_rate(self):
        # Get country from request (you'd need to implement IP geolocation)
        country = getattr(self.request, 'country_code', 'US')
        
        # Different limits per country
        country_limits = {
            'US': '1000/hour',
            'GB': '800/hour',
            'AE': '600/hour',
            'default': '200/hour'
        }
        
        return country_limits.get(country, country_limits['default'])