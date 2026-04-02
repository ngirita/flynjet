from django.db.models import Count, Sum, Avg
from django.utils import timezone
from .models import Dashboard, AnalyticsEvent, DailyMetric
from apps.bookings.models import Booking
from apps.accounts.models import User
import logging

logger = logging.getLogger(__name__)

class DashboardBuilder:
    """Build and manage dashboards"""
    
    @classmethod
    def create_default_dashboard(cls, user, dashboard_type='personal'):
        """Create default dashboard for user"""
        dashboard = Dashboard.objects.create(
            user=user,
            name=f"{user.get_full_name() or user.email}'s Dashboard",
            dashboard_type=dashboard_type,
            widgets=cls.get_default_widgets(dashboard_type),
            layout=cls.get_default_layout(dashboard_type)
        )
        
        logger.info(f"Created default {dashboard_type} dashboard for {user.email}")
        return dashboard
    
    @classmethod
    def get_default_widgets(cls, dashboard_type):
        """Get default widgets based on dashboard type"""
        if dashboard_type == 'admin':
            return [
                {
                    'id': 'revenue_chart',
                    'type': 'chart',
                    'title': 'Revenue Trend',
                    'config': {
                        'metric': 'revenue',
                        'period': '30d',
                        'chart_type': 'line'
                    }
                },
                {
                    'id': 'bookings_table',
                    'type': 'table',
                    'title': 'Recent Bookings',
                    'config': {
                        'limit': 10,
                        'columns': ['reference', 'user', 'amount', 'status']
                    }
                },
                {
                    'id': 'user_stats',
                    'type': 'kpi',
                    'title': 'User Statistics',
                    'config': {
                        'metrics': ['new_users', 'active_users', 'returning_users']
                    }
                },
                {
                    'id': 'fleet_utilization',
                    'type': 'chart',
                    'title': 'Fleet Utilization',
                    'config': {
                        'metric': 'utilization',
                        'chart_type': 'bar'
                    }
                }
            ]
        elif dashboard_type == 'agent':
            return [
                {
                    'id': 'my_bookings',
                    'type': 'table',
                    'title': 'My Assigned Bookings',
                    'config': {
                        'limit': 10,
                        'filter': 'assigned'
                    }
                },
                {
                    'id': 'performance',
                    'type': 'kpi',
                    'title': 'Performance',
                    'config': {
                        'metrics': ['bookings_handled', 'satisfaction', 'response_time']
                    }
                }
            ]
        else:  # personal
            return [
                {
                    'id': 'my_bookings',
                    'type': 'table',
                    'title': 'My Recent Bookings',
                    'config': {
                        'limit': 5,
                        'columns': ['reference', 'date', 'route', 'status']
                    }
                },
                {
                    'id': 'points_summary',
                    'type': 'kpi',
                    'title': 'Loyalty Points',
                    'config': {
                        'metrics': ['points_balance', 'tier', 'next_tier']
                    }
                }
            ]
    
    @classmethod
    def get_default_layout(cls, dashboard_type):
        """Get default layout for dashboard"""
        if dashboard_type == 'admin':
            return {
                'rows': [
                    {'columns': [{'width': 6, 'widgets': ['revenue_chart']},
                                 {'width': 6, 'widgets': ['user_stats']}]},
                    {'columns': [{'width': 12, 'widgets': ['bookings_table']}]},
                    {'columns': [{'width': 12, 'widgets': ['fleet_utilization']}]}
                ]
            }
        else:
            return {
                'rows': [
                    {'columns': [{'width': 12, 'widgets': ['my_bookings']}]},
                    {'columns': [{'width': 12, 'widgets': ['points_summary']}]}
                ]
            }
    
    @classmethod
    def get_dashboard_data(cls, dashboard):
        """Fetch data for dashboard widgets"""
        data = {}
        
        for widget in dashboard.widgets:
            widget_id = widget['id']
            widget_type = widget['type']
            config = widget['config']
            
            if widget_type == 'chart':
                data[widget_id] = cls.get_chart_data(config)
            elif widget_type == 'table':
                data[widget_id] = cls.get_table_data(config)
            elif widget_type == 'kpi':
                data[widget_id] = cls.get_kpi_data(config)
        
        return data
    
    @classmethod
    def get_chart_data(cls, config):
        """Get chart data based on configuration"""
        metric = config.get('metric')
        period = config.get('period', '30d')
        
        # Parse period
        if period.endswith('d'):
            days = int(period[:-1])
            start_date = timezone.now().date() - timezone.timedelta(days=days)
        else:
            start_date = timezone.now().date() - timezone.timedelta(days=30)
        
        # Get metrics from DailyMetric
        metrics = DailyMetric.objects.filter(
            date__gte=start_date
        ).order_by('date')
        
        if metric == 'revenue':
            return {
                'labels': [m.date.strftime('%Y-%m-%d') for m in metrics],
                'datasets': [{
                    'label': 'Revenue',
                    'data': [float(m.revenue) for m in metrics],
                    'borderColor': '#28a745'
                }]
            }
        elif metric == 'utilization':
            return {
                'labels': [m.date.strftime('%Y-%m-%d') for m in metrics],
                'datasets': [{
                    'label': 'Fleet Utilization',
                    'data': [float(m.fleet_utilization) for m in metrics],
                    'borderColor': '#007bff'
                }]
            }
        
        return {}
    
    @classmethod
    def get_table_data(cls, config):
        """Get table data based on configuration"""
        limit = config.get('limit', 10)
        
        if config.get('filter') == 'assigned':
            # This would need user context
            return []
        else:
            bookings = Booking.objects.all().order_by('-created_at')[:limit]
            return [{
                'reference': b.booking_reference,
                'user': b.user.email,
                'amount': float(b.total_amount_usd),
                'status': b.status,
                'date': b.created_at.isoformat()
            } for b in bookings]
    
    @classmethod
    def get_kpi_data(cls, config):
        """Get KPI data based on configuration"""
        metrics = config.get('metrics', [])
        data = {}
        
        for metric in metrics:
            if metric == 'new_users':
                data[metric] = User.objects.filter(
                    date_joined__date=timezone.now().date()
                ).count()
            elif metric == 'active_users':
                data[metric] = AnalyticsEvent.objects.filter(
                    timestamp__date=timezone.now().date()
                ).values('user').distinct().count()
            elif metric == 'points_balance':
                # This would need user context
                data[metric] = 0
        
        return data

class SharedDashboard:
    """Handle shared dashboards"""
    
    @classmethod
    def share_dashboard(cls, dashboard, expiry_hours=24):
        """Generate shareable link for dashboard"""
        dashboard.is_shared = True
        dashboard.share_expiry = timezone.now() + timezone.timedelta(hours=expiry_hours)
        dashboard.save(update_fields=['is_shared', 'share_expiry'])
        
        return dashboard.get_shareable_link()
    
    @classmethod
    def get_shared_dashboard(cls, token):
        """Get shared dashboard by token"""
        try:
            dashboard = Dashboard.objects.get(share_token=token, is_shared=True)
            
            if dashboard.share_expiry and dashboard.share_expiry < timezone.now():
                return None
            
            return dashboard
        except Dashboard.DoesNotExist:
            return None
    
    @classmethod
    def revoke_share(cls, dashboard):
        """Revoke shared access"""
        dashboard.is_shared = False
        dashboard.share_expiry = None
        dashboard.save(update_fields=['is_shared', 'share_expiry'])