from django.db.models import Q, Count, Sum, Avg
from django.utils import timezone
from apps.accounts.models import User
from apps.bookings.models import Booking
import pandas as pd
import numpy as np
import logging  

logger = logging.getLogger(__name__)

class CustomerSegmenter:
    """Segment customers based on behavior"""
    
    SEGMENTS = [
        'new', 'active', 'frequent', 'high_value', 'at_risk', 'churned', 'vip'
    ]
    
    @classmethod
    def segment_customers(cls):
        """Assign segments to all customers"""
        customers = User.objects.filter(is_active=True)
        
        for customer in customers:
            segment = cls.determine_segment(customer)
            if 'metadata' not in customer.__dict__:
                customer.metadata = {}
            customer.metadata['segment'] = segment
            customer.save(update_fields=['metadata'])
        
        logger.info(f"Segmented {customers.count()} customers")
    
    @classmethod
    def determine_segment(cls, user):
        """Determine segment for a single user"""
        # Get booking history
        bookings = user.bookings.all()
        total_bookings = bookings.count()
        
        if total_bookings == 0:
            return 'new'
        
        # Calculate metrics
        total_spent = bookings.aggregate(Sum('total_amount_usd'))['total_amount_usd__sum'] or 0
        last_booking = bookings.order_by('-created_at').first()
        days_since_last = (timezone.now() - last_booking.created_at).days if last_booking else 999
        
        # Segment logic
        if total_spent > 50000:
            return 'vip'
        elif total_bookings >= 10:
            return 'frequent'
        elif total_spent > 10000:
            return 'high_value'
        elif days_since_last <= 30:
            return 'active'
        elif 30 < days_since_last <= 90:
            return 'at_risk'
        else:
            return 'churned'
    
    @classmethod
    def get_segment_counts(cls):
        """Get count of customers in each segment"""
        counts = {}
        for segment in cls.SEGMENTS:
            counts[segment] = User.objects.filter(
                metadata__segment=segment
            ).count()
        return counts
    
    @classmethod
    def get_segment_customers(cls, segment):
        """Get customers in specific segment"""
        return User.objects.filter(metadata__segment=segment)

class RFMAnalyzer:
    """RFM (Recency, Frequency, Monetary) Analysis"""
    
    @classmethod
    def calculate_rfm(cls, user):
        """Calculate RFM scores for user"""
        bookings = user.bookings.filter(status='completed')
        
        if not bookings.exists():
            return {'r_score': 0, 'f_score': 0, 'm_score': 0, 'rfm_score': 0}
        
        # Recency: days since last booking
        last_booking = bookings.order_by('-created_at').first()
        days_since_last = (timezone.now() - last_booking.created_at).days
        r_score = cls.score_recency(days_since_last)
        
        # Frequency: number of bookings
        freq = bookings.count()
        f_score = cls.score_frequency(freq)
        
        # Monetary: total spent
        total_spent = bookings.aggregate(Sum('total_amount_usd'))['total_amount_usd__sum'] or 0
        m_score = cls.score_monetary(total_spent)
        
        rfm_score = r_score * 100 + f_score * 10 + m_score
        
        return {
            'r_score': r_score,
            'f_score': f_score,
            'm_score': m_score,
            'rfm_score': rfm_score
        }
    
    @classmethod
    def score_recency(cls, days):
        """Score recency (1-5)"""
        if days <= 7:
            return 5
        elif days <= 30:
            return 4
        elif days <= 60:
            return 3
        elif days <= 90:
            return 2
        else:
            return 1
    
    @classmethod
    def score_frequency(cls, count):
        """Score frequency (1-5)"""
        if count >= 20:
            return 5
        elif count >= 10:
            return 4
        elif count >= 5:
            return 3
        elif count >= 2:
            return 2
        else:
            return 1
    
    @classmethod
    def score_monetary(cls, amount):
        """Score monetary value (1-5)"""
        if amount >= 50000:
            return 5
        elif amount >= 25000:
            return 4
        elif amount >= 10000:
            return 3
        elif amount >= 5000:
            return 2
        else:
            return 1
    
    @classmethod
    def get_rfm_segments(cls):
        """Get RFM-based customer segments"""
        customers = User.objects.filter(is_active=True)
        segments = {
            'champions': [],
            'loyal': [],
            'potential': [],
            'new': [],
            'at_risk': [],
            'lost': []
        }
        
        for customer in customers:
            rfm = cls.calculate_rfm(customer)
            
            if rfm['rfm_score'] >= 400:
                segments['champions'].append(customer)
            elif rfm['rfm_score'] >= 300:
                segments['loyal'].append(customer)
            elif rfm['rfm_score'] >= 200:
                segments['potential'].append(customer)
            elif rfm['rfm_score'] >= 100:
                segments['new'].append(customer)
            elif rfm['rfm_score'] >= 50:
                segments['at_risk'].append(customer)
            else:
                segments['lost'].append(customer)
        
        return segments

class PredictiveAnalytics:
    """Predict customer behavior"""
    
    @classmethod
    def predict_churn(cls, user):
        """Predict churn probability"""
        bookings = user.bookings.all()
        
        if not bookings.exists():
            return 0.8  # High chance for new users
        
        # Factors
        days_since_last = (timezone.now() - bookings.order_by('-created_at').first().created_at).days
        booking_frequency = bookings.count() / max((timezone.now() - user.date_joined).days, 1)
        avg_spend = bookings.aggregate(Avg('total_amount_usd'))['total_amount_usd__avg'] or 0
        
        # Simple logistic regression (simplified)
        score = 0.3
        if days_since_last > 90:
            score += 0.4
        elif days_since_last > 60:
            score += 0.2
        
        if booking_frequency < 0.1:
            score += 0.2
        
        if avg_spend < 1000:
            score += 0.1
        
        return min(score, 1.0)
    
    @classmethod
    def predict_lifetime_value(cls, user, months=12):
        """Predict customer lifetime value"""
        bookings = user.bookings.filter(status='completed')
        
        if not bookings.exists():
            # No history - use average
            avg_booking_value = 5000
            expected_bookings = 2
            return avg_booking_value * expected_bookings
        
        # Calculate average booking value and frequency
        avg_booking_value = bookings.aggregate(Avg('total_amount_usd'))['total_amount_usd__avg'] or 0
        avg_days_between = (timezone.now() - user.date_joined).days / bookings.count()
        expected_bookings = months * 30 / max(avg_days_between, 1)
        
        # Apply growth factor for VIPs
        if user.user_type == 'corporate':
            expected_bookings *= 1.5
        
        return avg_booking_value * expected_bookings
    
    @classmethod
    def recommend_next_purchase(cls, user):
        """Recommend next purchase based on history"""
        bookings = user.bookings.select_related('aircraft').order_by('-created_at')
        
        if not bookings.exists():
            return None
        
        # Most recent aircraft
        last_aircraft = bookings.first().aircraft
        
        # Similar aircraft recommendation
        from apps.fleet.models import Aircraft
        similar = Aircraft.objects.filter(
            category=last_aircraft.category,
            passenger_capacity__range=(
                last_aircraft.passenger_capacity - 2,
                last_aircraft.passenger_capacity + 2
            )
        ).exclude(id=last_aircraft.id)[:3]
        
        return similar