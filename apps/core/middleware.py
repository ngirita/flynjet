import time
import logging
from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin
from django.db import close_old_connections

logger = logging.getLogger(__name__)


class AuditMiddleware(MiddlewareMixin):
    """Middleware to log user activities with safe connection handling."""
    
    def process_request(self, request):
        """Process request safely."""
        # Close old connections
        close_old_connections()
        
        # Store request start time
        request.start_time = time.time()
        return None
    
    def process_response(self, request, response):
        """Process response and log activities."""
        try:
            # Close old connections after response
            close_old_connections()
            
            # Log activity for authenticated users
            if hasattr(request, 'user') and request.user.is_authenticated:
                if request.method in ['POST', 'PUT', 'DELETE']:
                    self.log_activity(request, response)
                
                # Update last activity safely
                try:
                    request.user.last_activity = timezone.now()
                    request.user.save(update_fields=['last_activity'])
                except Exception as e:
                    logger.error(f"Failed to update last activity: {e}")
                    
        except Exception as e:
            logger.error(f"Audit middleware error: {e}")
        
        return response
    
    def log_activity(self, request, response):
        """Log user activity."""
        try:
            from .models import ActivityLog
            
            # Don't log every request, only important ones
            if request.path.startswith('/admin/') or request.path.startswith('/api/'):
                ActivityLog.objects.create(
                    user=request.user,
                    activity_type='admin_action' if request.path.startswith('/admin/') else 'api_call',
                    description=f"{request.method} {request.path}",
                    ip_address=self.get_client_ip(request),
                    user_agent=request.META.get('HTTP_USER_AGENT', '')[:255],
                    data={
                        'method': request.method,
                        'path': request.path,
                        'status_code': response.status_code,
                        'query_params': dict(request.GET),
                    }
                )
        except Exception as e:
            logger.error(f"Failed to log activity: {e}")
    
    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class TimezoneMiddleware(MiddlewareMixin):
    """Middleware to set timezone based on user preference."""
    
    def process_request(self, request):
        """Set timezone safely."""
        try:
            if hasattr(request, 'user') and request.user.is_authenticated:
                # Check if user has profile and timezone field
                if hasattr(request.user, 'profile') and hasattr(request.user.profile, 'timezone'):
                    tz = request.user.profile.timezone
                    timezone.activate(tz)
                else:
                    timezone.activate('UTC')
            else:
                timezone.activate('UTC')
        except Exception as e:
            logger.error(f"Timezone middleware error: {e}")
            timezone.activate('UTC')
        
        return None


class MaintenanceModeMiddleware(MiddlewareMixin):
    """Middleware to handle maintenance mode."""
    
    def process_request(self, request):
        """Check maintenance mode."""
        try:
            from .models import SiteSettings
            settings = SiteSettings.get_settings()
            
            if settings.enable_maintenance_mode:
                # Allow access to admin and staff
                if request.path.startswith('/admin/') or (hasattr(request, 'user') and request.user.is_staff):
                    return None
                
                # Check if IP is allowed
                client_ip = self.get_client_ip(request)
                if client_ip in settings.maintenance_allowed_ips:
                    return None
                
                # Show maintenance page
                from django.shortcuts import render
                return render(request, 'maintenance.html', {
                    'message': settings.maintenance_message
                }, status=503)
        except Exception as e:
            logger.error(f"Maintenance middleware error: {e}")
        
        return None
    
    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class RateLimitMiddleware(MiddlewareMixin):
    """Simple rate limiting middleware with safe connection handling."""
    
    def __init__(self, get_response):
        super().__init__(get_response)
        self.request_counts = {}
    
    def process_request(self, request):
        """Apply rate limiting."""
        try:
            # Get key based on user or IP
            if hasattr(request, 'user') and request.user.is_authenticated:
                key = f"user_{request.user.id}"
            else:
                key = f"ip_{self.get_client_ip(request)}"
            
            # Check rate limit
            if not self.check_rate_limit(key, request.path):
                from django.http import HttpResponse
                return HttpResponse(
                    "Rate limit exceeded. Please try again later.",
                    status=429,
                    content_type='text/plain'
                )
        except Exception as e:
            logger.error(f"Rate limit middleware error: {e}")
        
        return None
    
    def check_rate_limit(self, key, path):
        """Check if request is within rate limits."""
        now = time.time()
        
        # Clean old entries (keep last 5 minutes)
        self.request_counts = {
            k: [t for t in times if now - t < 300]
            for k, times in self.request_counts.items()
        }
        
        # Check if key exists
        if key not in self.request_counts:
            self.request_counts[key] = []
        
        # Count requests in the window
        recent_requests = len(self.request_counts[key])
        
        # Set limits
        if path.startswith('/api/'):
            limit = 10000
        elif path.startswith('/admin/'):
            limit = 5000
        else:
            limit = 3000
        
        # Check per minute limit
        minute_count = sum(1 for t in self.request_counts[key] if now - t < 60)
        minute_limit = 1000
        
        if recent_requests >= limit or minute_count >= minute_limit:
            return False
        
        self.request_counts[key].append(now)
        return True
    
    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip