from django.db.models import Count, Sum, Avg
from django.utils import timezone
from .models import DailyMetric, AnalyticsEvent
from apps.bookings.models import Booking
from apps.payments.models import Payment
from apps.accounts.models import User
import logging

logger = logging.getLogger(__name__)

class MetricsCalculator:
    """Calculate various business metrics"""
    
    @classmethod
    def calculate_daily_metrics(cls, date=None):
        """Calculate metrics for a specific date"""
        if date is None:
            date = timezone.now().date()
        
        # Get or create daily metric
        metric, created = DailyMetric.objects.get_or_create(date=date)
        
        # User metrics
        metric.new_users = User.objects.filter(date_joined__date=date).count()
        metric.active_users = AnalyticsEvent.objects.filter(
            timestamp__date=date
        ).values('user').distinct().count()
        
        # Booking metrics
        bookings = Booking.objects.filter(created_at__date=date)
        metric.total_bookings = bookings.count()
        metric.completed_bookings = bookings.filter(status='completed').count()
        metric.cancelled_bookings = bookings.filter(status='cancelled').count()
        
        booking_value = bookings.aggregate(Sum('total_amount_usd'))['total_amount_usd__sum'] or 0
        metric.booking_value = booking_value
        metric.average_booking_value = booking_value / metric.total_bookings if metric.total_bookings > 0 else 0
        
        # Revenue metrics
        payments = Payment.objects.filter(created_at__date=date, status='completed')
        metric.revenue = payments.aggregate(Sum('amount_usd'))['amount_usd__sum'] or 0
        
        refunds = Payment.objects.filter(created_at__date=date, status='refunded')
        metric.refunds = refunds.aggregate(Sum('amount_usd'))['amount_usd__sum'] or 0
        metric.net_revenue = metric.revenue - metric.refunds
        
        # Payment metrics
        metric.payment_success = payments.count()
        metric.payment_failed = Payment.objects.filter(
            created_at__date=date,
            status='failed'
        ).count()
        
        # Payment method breakdown
        method_breakdown = {}
        for payment in payments:
            method = payment.payment_method
            method_breakdown[method] = method_breakdown.get(method, 0) + payment.amount_usd
        metric.payment_method_breakdown = method_breakdown
        
        # Traffic metrics
        metric.page_views = AnalyticsEvent.objects.filter(
            timestamp__date=date,
            event_type='page_view'
        ).count()
        
        metric.unique_visitors = AnalyticsEvent.objects.filter(
            timestamp__date=date
        ).values('anonymous_id').distinct().count()
        
        metric.save()
        logger.info(f"Calculated daily metrics for {date}")
        return metric
    
    @classmethod
    def calculate_metrics_range(cls, start_date, end_date):
        """Calculate metrics for date range"""
        metrics = []
        current_date = start_date
        
        while current_date <= end_date:
            metric = cls.calculate_daily_metrics(current_date)
            metrics.append(metric)
            current_date += timezone.timedelta(days=1)
        
        return metrics
    
    @classmethod
    def get_kpi_summary(cls):
        """Get summary of key KPIs"""
        today = timezone.now().date()
        yesterday = today - timezone.timedelta(days=1)
        last_week = today - timezone.timedelta(days=7)
        
        # Today's metrics
        today_metric = cls.calculate_daily_metrics(today)
        
        # Yesterday's metrics
        yesterday_metric = cls.calculate_daily_metrics(yesterday)
        
        # Weekly averages
        weekly_metrics = DailyMetric.objects.filter(
            date__gte=last_week,
            date__lte=yesterday
        )
        
        return {
            'today': {
                'revenue': float(today_metric.revenue),
                'bookings': today_metric.total_bookings,
                'users': today_metric.new_users,
                'page_views': today_metric.page_views
            },
            'vs_yesterday': {
                'revenue_change': cls.calculate_change(today_metric.revenue, yesterday_metric.revenue),
                'bookings_change': cls.calculate_change(today_metric.total_bookings, yesterday_metric.total_bookings),
                'users_change': cls.calculate_change(today_metric.new_users, yesterday_metric.new_users)
            },
            'weekly_avg': {
                'revenue': float(weekly_metrics.aggregate(Avg('revenue'))['revenue__avg'] or 0),
                'bookings': float(weekly_metrics.aggregate(Avg('total_bookings'))['total_bookings__avg'] or 0),
                'users': float(weekly_metrics.aggregate(Avg('new_users'))['new_users__avg'] or 0)
            }
        }
    
    @classmethod
    def calculate_change(cls, current, previous):
        """Calculate percentage change"""
        if previous == 0:
            return 100 if current > 0 else 0
        return ((current - previous) / previous) * 100

class EventTracker:
    """Track user events for analytics"""
    
    @classmethod
    def track_event(cls, request, event_type, data=None):
        """Track a user event"""
        event = AnalyticsEvent.objects.create(
            event_id=cls.generate_event_id(),
            event_type=event_type,
            timestamp=timezone.now(),
            user=request.user if request.user.is_authenticated else None,
            anonymous_id=request.session.session_key,
            session_id=request.session.session_key,
            url=request.build_absolute_uri(),
            referrer=request.META.get('HTTP_REFERER', ''),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            ip_address=cls.get_client_ip(request),
            data=data or {}
        )
        
        logger.info(f"Tracked event {event_type} for {request.user.email if request.user.is_authenticated else 'anonymous'}")
        return event
    
    @classmethod
    def get_client_ip(cls, request):
        """Get client IP from request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    @classmethod
    def generate_event_id(cls):
        """Generate unique event ID"""
        import uuid
        return str(uuid.uuid4())

class PerformanceMetrics:
    """Track system performance metrics"""
    
    @classmethod
    def track_response_time(cls, view_name, duration):
        """Track view response time"""
        # Implementation would store in time-series database
        logger.info(f"Response time for {view_name}: {duration:.2f}s")
    
    @classmethod
    def track_error(cls, error_type, message):
        """Track errors"""
        logger.error(f"Error: {error_type} - {message}")
    
    @classmethod
    def get_performance_report(cls):
        """Get performance report"""
        return {
            'avg_response_time': 0.5,  # Placeholder
            'error_rate': 0.01,
            'uptime': 99.9,
            'active_users': 100
        }