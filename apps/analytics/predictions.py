import numpy as np
from django.utils import timezone
from django.db.models import Sum, Count, Avg
from .models import DailyMetric
from apps.bookings.models import Booking
import logging

logger = logging.getLogger(__name__)

class DemandForecaster:
    """Predict future demand"""
    
    @classmethod
    def forecast_bookings(cls, days_ahead=30):
        """Forecast booking volume for next N days"""
        # Get historical data
        end_date = timezone.now().date()
        start_date = end_date - timezone.timedelta(days=90)
        
        history = DailyMetric.objects.filter(
            date__gte=start_date,
            date__lte=end_date
        ).order_by('date')
        
        if not history.exists():
            return []
        
        # Simple moving average forecast
        recent = list(history.values_list('total_bookings', flat=True))[-30:]
        avg = sum(recent) / len(recent)
        
        # Add trend factor
        if len(recent) > 7:
            trend = (recent[-1] - recent[-7]) / 7
        else:
            trend = 0
        
        forecast = []
        for i in range(days_ahead):
            # Add seasonality (weekend effect)
            date = end_date + timezone.timedelta(days=i+1)
            weekend_multiplier = 1.2 if date.weekday() >= 5 else 1.0
            
            predicted = (avg + trend * (i+1)) * weekend_multiplier
            forecast.append({
                'date': date,
                'predicted_bookings': int(max(0, predicted)),
                'lower_bound': int(max(0, predicted * 0.8)),
                'upper_bound': int(predicted * 1.2)
            })
        
        return forecast
    
    @classmethod
    def forecast_revenue(cls, days_ahead=30):
        """Forecast revenue for next N days"""
        bookings_forecast = cls.forecast_bookings(days_ahead)
        
        # Get average booking value
        avg_value = DailyMetric.objects.aggregate(
            avg=Avg('average_booking_value')
        )['avg'] or 5000
        
        forecast = []
        for item in bookings_forecast:
            forecast.append({
                'date': item['date'],
                'predicted_revenue': item['predicted_bookings'] * avg_value,
                'lower_bound': item['lower_bound'] * avg_value,
                'upper_bound': item['upper_bound'] * avg_value
            })
        
        return forecast
    
    @classmethod
    def detect_trends(cls):
        """Detect current trends in the data"""
        end_date = timezone.now().date()
        start_date = end_date - timezone.timedelta(days=30)
        
        current = DailyMetric.objects.filter(
            date__gte=start_date,
            date__lte=end_date
        ).aggregate(
            total_bookings=Sum('total_bookings'),
            total_revenue=Sum('revenue')
        )
        
        previous_start = start_date - timezone.timedelta(days=30)
        previous = DailyMetric.objects.filter(
            date__gte=previous_start,
            date__lt=start_date
        ).aggregate(
            total_bookings=Sum('total_bookings'),
            total_revenue=Sum('revenue')
        )
        
        trends = {}
        for metric in ['total_bookings', 'total_revenue']:
            current_val = current.get(metric, 0) or 0
            prev_val = previous.get(metric, 0) or 0
            
            if prev_val > 0:
                change = ((current_val - prev_val) / prev_val) * 100
                trends[metric] = {
                    'current': float(current_val),
                    'previous': float(prev_val),
                    'change_percent': float(change),
                    'trend': 'up' if change > 0 else 'down' if change < 0 else 'stable'
                }
            else:
                trends[metric] = {
                    'current': float(current_val),
                    'previous': 0,
                    'change_percent': 0,
                    'trend': 'stable'
                }
        
        return trends

class CustomerPredictor:
    """Predict customer behavior"""
    
    @classmethod
    def predict_churn_probability(cls, user):
        """Predict probability of customer churning"""
        from apps.accounts.models import User
        
        # Factors
        days_since_last_booking = cls.get_days_since_last_booking(user)
        booking_frequency = cls.get_booking_frequency(user)
        avg_spend = cls.get_average_spend(user)
        
        # Weighted score
        score = 0
        if days_since_last_booking > 90:
            score += 0.4
        elif days_since_last_booking > 60:
            score += 0.2
        
        if booking_frequency < 0.1:  # Less than 1 booking per 10 days
            score += 0.3
        
        if avg_spend < 1000:
            score += 0.1
        
        # User type factor
        if user.user_type == 'corporate':
            score *= 0.5  # Corporate clients less likely to churn
        
        return min(score, 1.0)
    
    @classmethod
    def predict_lifetime_value(cls, user, months=12):
        """Predict customer lifetime value"""
        from apps.accounts.models import User
        
        bookings = user.bookings.filter(status='completed')
        
        if not bookings.exists():
            # No history - use average
            avg_booking_value = 5000
            expected_bookings = 2
            return avg_booking_value * expected_bookings
        
        # Calculate average booking value and frequency
        avg_booking_value = bookings.aggregate(Avg('total_amount_usd'))['total_amount_usd__avg'] or 0
        days_active = (timezone.now() - user.date_joined).days
        booking_frequency = bookings.count() / max(days_active, 1)
        
        expected_bookings = booking_frequency * 30 * months
        
        # Apply growth factor for VIPs
        if user.user_type == 'corporate':
            expected_bookings *= 1.5
        
        return avg_booking_value * expected_bookings
    
    @classmethod
    def get_days_since_last_booking(cls, user):
        """Get days since user's last booking"""
        last_booking = user.bookings.order_by('-created_at').first()
        if last_booking:
            return (timezone.now() - last_booking.created_at).days
        return 999
    
    @classmethod
    def get_booking_frequency(cls, user):
        """Get average bookings per day"""
        bookings = user.bookings.count()
        days_active = (timezone.now() - user.date_joined).days
        return bookings / max(days_active, 1)
    
    @classmethod
    def get_average_spend(cls, user):
        """Get average spend per booking"""
        avg = user.bookings.aggregate(Avg('total_amount_usd'))['total_amount_usd__avg']
        return avg or 0

class FleetOptimizer:
    """Optimize fleet utilization"""
    
    @classmethod
    def recommend_aircraft_purchase(cls):
        """Recommend aircraft purchase based on demand"""
        from apps.fleet.models import Aircraft
        
        # Analyze current utilization
        aircraft = Aircraft.objects.all()
        utilization = []
        
        for a in aircraft:
            bookings = a.bookings.filter(status='completed')
            total_hours = sum(
                (b.arrival_datetime - b.departure_datetime).total_seconds() / 3600
                for b in bookings
            )
            utilization.append({
                'aircraft': a,
                'utilization': total_hours / (24 * 30) * 100 if total_hours > 0 else 0,
                'revenue': bookings.aggregate(Sum('total_amount_usd'))['total_amount_usd__sum'] or 0
            })
        
        # Identify high-demand categories
        category_demand = {}
        for u in utilization:
            cat = u['aircraft'].category.name
            if cat not in category_demand:
                category_demand[cat] = {'utilization': 0, 'count': 0}
            category_demand[cat]['utilization'] += u['utilization']
            category_demand[cat]['count'] += 1
        
        recommendations = []
        for cat, data in category_demand.items():
            avg_util = data['utilization'] / data['count']
            if avg_util > 70:  # High utilization
                recommendations.append({
                    'category': cat,
                    'avg_utilization': avg_util,
                    'recommendation': 'Consider adding more aircraft',
                    'priority': 'high' if avg_util > 85 else 'medium'
                })
        
        return recommendations
    
    @classmethod
    def optimize_scheduling(cls, date):
        """Optimize flight scheduling for a given date"""
        from apps.fleet.models import Aircraft
        from apps.bookings.models import Booking
        
        bookings = Booking.objects.filter(
            departure_datetime__date=date,
            status__in=['confirmed', 'paid']
        ).order_by('departure_datetime')
        
        schedule = []
        for booking in bookings:
            schedule.append({
                'time': booking.departure_datetime,
                'aircraft': booking.aircraft.registration_number,
                'route': f"{booking.departure_airport} → {booking.arrival_airport}",
                'duration': (booking.arrival_datetime - booking.departure_datetime).total_seconds() / 3600
            })
        
        return schedule