import logging
from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.http import HttpResponseForbidden, JsonResponse
from django.core.cache import cache
from .models import SiteSettings

# Set up logger
logger = logging.getLogger(__name__)

def staff_required(function=None, redirect_url='core:home'):
    """Decorator to require staff access"""
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                messages.error(request, "Please login to access this page.")
                return redirect('accounts:login')
            
            if not (request.user.is_staff or request.user.user_type == 'admin'):
                messages.error(request, "You don't have permission to access this page.")
                return redirect(redirect_url)
            
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    
    if function:
        return decorator(function)
    return decorator

def admin_required(function=None):
    """Decorator to require admin access"""
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                    return JsonResponse({'error': 'Authentication required'}, status=401)
                messages.error(request, "Please login to access this page.")
                return redirect('accounts:login')
            
            if not (request.user.is_superuser or request.user.user_type == 'admin'):
                if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                    return JsonResponse({'error': 'Permission denied'}, status=403)
                messages.error(request, "Admin access required.")
                return redirect('core:home')
            
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    
    if function:
        return decorator(function)
    return decorator

def ajax_required(function=None):
    """Decorator to require AJAX request"""
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return HttpResponseForbidden("This endpoint only accepts AJAX requests.")
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    
    if function:
        return decorator(function)
    return decorator

def rate_limit(key_func=None, rate='100/h', method='ALL'):
    """
    Decorator to rate limit views
    Usage: @rate_limit(key_func=lambda r: r.user.id, rate='10/m')
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if request.method.upper() != method and method != 'ALL':
                return view_func(request, *args, **kwargs)
            
            # Get cache key
            if key_func:
                key = f"rate_limit:{key_func(request)}"
            elif request.user.is_authenticated:
                key = f"rate_limit:user:{request.user.id}"
            else:
                key = f"rate_limit:ip:{request.META.get('REMOTE_ADDR', '')}"
            
            # Parse rate (e.g., '100/h' -> 100, 3600)
            try:
                limit, period = rate.split('/')
                limit = int(limit)
                if period == 'h':
                    timeout = 3600
                elif period == 'm':
                    timeout = 60
                elif period == 'd':
                    timeout = 86400
                else:
                    timeout = int(period)
            except:
                limit, timeout = 100, 3600
            
            # Check cache
            count = cache.get(key, 0)
            if count >= limit:
                if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                    return JsonResponse({
                        'error': 'Rate limit exceeded',
                        'retry_after': timeout
                    }, status=429)
                messages.error(request, f"Too many requests. Please try again later.")
                return redirect('core:home')
            
            # Increment counter
            cache.set(key, count + 1, timeout)
            
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    
    if function:
        return decorator(function)
    return decorator

def maintenance_mode_check(function=None):
    """Decorator to check maintenance mode"""
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            settings = SiteSettings.get_settings()
            
            if settings.enable_maintenance_mode:
                # Allow staff to bypass
                if request.user.is_authenticated and request.user.is_staff:
                    return view_func(request, *args, **kwargs)
                
                # Check allowed IPs
                client_ip = request.META.get('REMOTE_ADDR', '')
                if client_ip in settings.maintenance_allowed_ips:
                    return view_func(request, *args, **kwargs)
                
                # Show maintenance page
                return redirect('core:maintenance')
            
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    
    if function:
        return decorator(function)
    return decorator

def log_activity(activity_type=None):
    """Decorator to log user activity"""
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            response = view_func(request, *args, **kwargs)
            
            if request.user.is_authenticated and response.status_code < 400:
                from .models import ActivityLog
                ActivityLog.objects.create(
                    user=request.user,
                    activity_type=activity_type or 'view',
                    description=f"Accessed {request.path}",
                    ip_address=request.META.get('REMOTE_ADDR', ''),
                    user_agent=request.META.get('HTTP_USER_AGENT', ''),
                    data={'method': request.method, 'path': request.path}
                )
            
            return response
        return _wrapped_view
    
    return decorator

def cache_page(timeout=300, key_prefix=None):
    """Decorator to cache view response"""
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            # Don't cache for authenticated users or POST requests
            if request.user.is_authenticated or request.method != 'GET':
                return view_func(request, *args, **kwargs)
            
            # Generate cache key
            key = f"view_cache:{key_prefix or ''}:{request.path}:{request.GET.urlencode()}"
            
            # Try to get from cache
            response = cache.get(key)
            if response:
                return response
            
            # Generate and cache response
            response = view_func(request, *args, **kwargs)
            cache.set(key, response, timeout)
            
            return response
        return _wrapped_view
    
    return decorator

def permission_required(permission, redirect_url='core:home'):
    """Decorator to check specific permission"""
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                messages.error(request, "Please login to access this page.")
                return redirect('accounts:login')
            
            if not request.user.has_perm(permission):
                messages.error(request, "You don't have permission to perform this action.")
                return redirect(redirect_url)
            
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    
    return decorator

def condition(condition_func, redirect_url=None):
    """Decorator to check condition before executing view"""
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if condition_func(request):
                return view_func(request, *args, **kwargs)
            
            if redirect_url:
                return redirect(redirect_url)
            
            return HttpResponseForbidden("Condition not met.")
        return _wrapped_view
    
    return decorator

def handle_exceptions(view_func):
    """Decorator to handle exceptions gracefully"""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        try:
            return view_func(request, *args, **kwargs)
        except Exception as e:
            logger.error(f"Error in {view_func.__name__}: {e}", exc_info=True)
            
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'error': str(e)}, status=500)
            
            messages.error(request, "An error occurred. Please try again.")
            return redirect('core:home')
    
    return _wrapped_view

def time_monitor(view_func):
    """Decorator to monitor view execution time"""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        import time
        start = time.time()
        response = view_func(request, *args, **kwargs)
        duration = time.time() - start
        
        # Log slow views (> 1 second)
        if duration > 1:
            logger.warning(f"Slow view: {view_func.__name__} took {duration:.2f}s")
        
        return response
    
    return _wrapped_view