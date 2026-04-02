from datetime import datetime, timedelta
from django.db.models import Q
from django.utils import timezone
from .models import Booking
from apps.fleet.models import Aircraft

class AvailabilityChecker:
    """Check aircraft availability"""
    
    @classmethod
    def check_aircraft_availability(cls, aircraft_id, start_datetime, end_datetime):
        """Check if aircraft is available for given time slot"""
        conflicting_bookings = Booking.objects.filter(
            aircraft_id=aircraft_id,
            status__in=['confirmed', 'paid', 'in_progress'],
            departure_datetime__lt=end_datetime,
            arrival_datetime__gt=start_datetime
        ).exists()
        
        return not conflicting_bookings
    
    @classmethod
    def find_available_aircraft(cls, start_datetime, end_datetime, 
                                 passengers=None, aircraft_type=None):
        """Find available aircraft for given time slot"""
        queryset = Aircraft.objects.filter(
            is_active=True,
            status='available'
        )
        
        if passengers:
            queryset = queryset.filter(passenger_capacity__gte=passengers)
        
        if aircraft_type:
            queryset = queryset.filter(category__category_type=aircraft_type)
        
        # Exclude aircraft with conflicting bookings
        booked_aircraft = Booking.objects.filter(
            status__in=['confirmed', 'paid', 'in_progress'],
            departure_datetime__lt=end_datetime,
            arrival_datetime__gt=start_datetime
        ).values_list('aircraft_id', flat=True)
        
        available = queryset.exclude(id__in=booked_aircraft)
        
        return available
    
    @classmethod
    def get_availability_calendar(cls, aircraft_id, start_date, end_date):
        """Get availability calendar for date range"""
        aircraft = Aircraft.objects.get(id=aircraft_id)
        
        bookings = Booking.objects.filter(
            aircraft=aircraft,
            status__in=['confirmed', 'paid', 'in_progress'],
            departure_datetime__date__gte=start_date,
            departure_datetime__date__lte=end_date
        ).order_by('departure_datetime')
        
        calendar = []
        current_date = start_date
        
        while current_date <= end_date:
            day_bookings = [
                b for b in bookings 
                if b.departure_datetime.date() <= current_date <= b.arrival_datetime.date()
            ]
            
            calendar.append({
                'date': current_date,
                'is_available': len(day_bookings) == 0,
                'bookings': [
                    {
                        'id': b.id,
                        'reference': b.booking_reference,
                        'start': b.departure_datetime,
                        'end': b.arrival_datetime
                    }
                    for b in day_bookings
                ]
            })
            
            current_date += timedelta(days=1)
        
        return calendar
    
    @classmethod
    def get_next_available_slot(cls, aircraft_id, duration_hours, start_from=None):
        """Find next available time slot of given duration"""
        if start_from is None:
            start_from = timezone.now()
        
        aircraft = Aircraft.objects.get(id=aircraft_id)
        end_needed = start_from + timedelta(hours=duration_hours)
        
        # Get future bookings
        future_bookings = Booking.objects.filter(
            aircraft=aircraft,
            status__in=['confirmed', 'paid', 'in_progress'],
            departure_datetime__gte=start_from
        ).order_by('departure_datetime')
        
        # Check if initial slot is available
        if not future_bookings.filter(
            departure_datetime__lt=end_needed,
            arrival_datetime__gt=start_from
        ).exists():
            return start_from
        
        # Find gap between bookings
        last_end = start_from
        for booking in future_bookings:
            if booking.departure_datetime > last_end + timedelta(hours=duration_hours):
                # Found a gap
                return last_end
            last_end = max(last_end, booking.arrival_datetime)
        
        # If no gap found, return after last booking
        return last_end
    
    @classmethod
    def calculate_utilization_rate(cls, aircraft_id, start_date, end_date):
        """Calculate aircraft utilization rate for period"""
        aircraft = Aircraft.objects.get(id=aircraft_id)
        
        bookings = Booking.objects.filter(
            aircraft=aircraft,
            status__in=['confirmed', 'paid', 'completed'],
            departure_datetime__date__gte=start_date,
            arrival_datetime__date__lte=end_date
        )
        
        total_hours = 0
        period_hours = (end_date - start_date).days * 24
        
        for booking in bookings:
            duration = booking.arrival_datetime - booking.departure_datetime
            total_hours += duration.total_seconds() / 3600
        
        utilization = (total_hours / period_hours) * 100 if period_hours > 0 else 0
        return min(utilization, 100)