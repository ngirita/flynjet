from datetime import datetime, timedelta
from django.db.models import Q
from django.utils import timezone
from .models import Aircraft, AircraftMaintenance
import logging

logger = logging.getLogger(__name__)

class MaintenanceScheduler:
    """Schedule and manage aircraft maintenance"""
    
    MAINTENANCE_INTERVALS = {
        'A': 100,  # A-check every 100 flight hours
        'B': 500,  # B-check every 500 flight hours
        'C': 1500,  # C-check every 1500 flight hours
        'D': 6000,  # D-check every 6000 flight hours
    }
    
    @classmethod
    def schedule_routine_maintenance(cls, aircraft_id):
        """Schedule routine maintenance based on flight hours"""
        try:
            aircraft = Aircraft.objects.get(id=aircraft_id)
            
            next_maintenance = {}
            for check_type, interval in cls.MAINTENANCE_INTERVALS.items():
                if aircraft.total_flight_hours % interval < 50:
                    # Due for maintenance soon
                    due_date = timezone.now() + timedelta(days=7)
                    next_maintenance[check_type] = due_date
            
            return next_maintenance
        except Aircraft.DoesNotExist:
            logger.error(f"Aircraft {aircraft_id} not found")
            return {}
    
    @classmethod
    def check_maintenance_due(cls):
        """Check all aircraft for due maintenance"""
        due_maintenance = []
        
        for aircraft in Aircraft.objects.filter(is_active=True):
            next_due = cls.get_next_maintenance_due(aircraft)
            if next_due and next_due <= timezone.now() + timedelta(days=7):
                due_maintenance.append({
                    'aircraft': aircraft,
                    'due_date': next_due,
                    'hours_remaining': cls.get_hours_until_maintenance(aircraft)
                })
        
        return due_maintenance
    
    @classmethod
    def get_next_maintenance_due(cls, aircraft):
        """Get next maintenance due date"""
        if aircraft.next_maintenance_due:
            return aircraft.next_maintenance_due
        
        # Calculate based on flight hours
        for check_type, interval in cls.MAINTENANCE_INTERVALS.items():
            hours_to_next = interval - (aircraft.total_flight_hours % interval)
            if hours_to_next < 50:  # Due within 50 hours
                # Convert to estimated date based on average daily usage
                daily_usage = 8  # Average 8 hours per day
                days_to_due = hours_to_next / daily_usage
                return timezone.now() + timedelta(days=days_to_due)
        
        return None
    
    @classmethod
    def get_hours_until_maintenance(cls, aircraft):
        """Get hours until next maintenance"""
        min_hours = float('inf')
        
        for interval in cls.MAINTENANCE_INTERVALS.values():
            hours_to = interval - (aircraft.total_flight_hours % interval)
            min_hours = min(min_hours, hours_to)
        
        return min_hours
    
    @classmethod
    def create_maintenance_record(cls, aircraft, maintenance_type, scheduled_date, notes=""):
        """Create a new maintenance record"""
        end_date = scheduled_date + timedelta(days=cls.get_maintenance_duration(maintenance_type))
        
        maintenance = AircraftMaintenance.objects.create(
            aircraft=aircraft,
            maintenance_type=maintenance_type,
            status='scheduled',
            title=f"{maintenance_type}-Check Maintenance",
            description=notes or f"Scheduled {maintenance_type}-check maintenance",
            scheduled_start=scheduled_date,
            scheduled_end=end_date,
            estimated_cost_usd=cls.get_estimated_cost(aircraft, maintenance_type)
        )
        
        logger.info(f"Created maintenance record {maintenance.id} for {aircraft.registration_number}")
        return maintenance
    
    @classmethod
    def get_maintenance_duration(cls, maintenance_type):
        """Get estimated duration in days for maintenance type"""
        durations = {
            'A': 1,
            'B': 3,
            'C': 7,
            'D': 14,
            'scheduled': 2,
            'unscheduled': 3,
            'inspection': 1,
            'overhaul': 10,
        }
        return durations.get(maintenance_type, 2)
    
    @classmethod
    def get_estimated_cost(cls, aircraft, maintenance_type):
        """Get estimated cost for maintenance type"""
        base_costs = {
            'A': 5000,
            'B': 15000,
            'C': 50000,
            'D': 150000,
            'scheduled': 10000,
            'unscheduled': 20000,
            'inspection': 3000,
            'overhaul': 75000,
        }
        
        # Adjust based on aircraft size/age
        base = base_costs.get(maintenance_type, 10000)
        size_multiplier = aircraft.passenger_capacity / 10
        age_multiplier = 1 + (aircraft.age * 0.05)
        
        return base * size_multiplier * age_multiplier
    
    @classmethod
    def reschedule_maintenance(cls, maintenance_id, new_date):
        """Reschedule maintenance"""
        try:
            maintenance = AircraftMaintenance.objects.get(id=maintenance_id)
            old_date = maintenance.scheduled_start
            maintenance.scheduled_start = new_date
            maintenance.scheduled_end = new_date + timedelta(
                days=cls.get_maintenance_duration(maintenance.maintenance_type)
            )
            maintenance.save()
            
            logger.info(f"Rescheduled maintenance {maintenance_id} from {old_date} to {new_date}")
            return maintenance
        except AircraftMaintenance.DoesNotExist:
            logger.error(f"Maintenance {maintenance_id} not found")
            return None
    
    @classmethod
    def cancel_maintenance(cls, maintenance_id, reason):
        """Cancel scheduled maintenance"""
        try:
            maintenance = AircraftMaintenance.objects.get(id=maintenance_id)
            maintenance.status = 'cancelled'
            maintenance.save()
            
            logger.info(f"Cancelled maintenance {maintenance_id}: {reason}")
            return True
        except AircraftMaintenance.DoesNotExist:
            logger.error(f"Maintenance {maintenance_id} not found")
            return False
    
    @classmethod
    def get_maintenance_history(cls, aircraft_id, months=12):
        """Get maintenance history for aircraft"""
        start_date = timezone.now() - timedelta(days=30 * months)
        
        return AircraftMaintenance.objects.filter(
            aircraft_id=aircraft_id,
            completed_at__gte=start_date
        ).order_by('-completed_at')

class MaintenancePredictor:
    """Predict future maintenance needs"""
    
    @classmethod
    def predict_next_maintenance(cls, aircraft):
        """Predict next maintenance date based on historical data"""
        # Get historical maintenance
        history = AircraftMaintenance.objects.filter(
            aircraft=aircraft,
            status='completed'
        ).order_by('-completed_at')
        
        if not history.exists():
            return None
        
        # Calculate average interval between maintenances
        intervals = []
        prev_date = None
        for maintenance in history:
            if prev_date:
                interval = (prev_date - maintenance.completed_at).days
                intervals.append(interval)
            prev_date = maintenance.completed_at
        
        if intervals:
            avg_interval = sum(intervals) / len(intervals)
            predicted_date = timezone.now() + timedelta(days=avg_interval)
            return predicted_date
        
        return None
    
    @classmethod
    def predict_maintenance_cost(cls, aircraft, months=12):
        """Predict maintenance costs for next period"""
        # Get historical costs
        history = AircraftMaintenance.objects.filter(
            aircraft=aircraft,
            completed_at__gte=timezone.now() - timedelta(days=365)
        )
        
        if not history.exists():
            return 5000 * (months / 12)  # Default estimate
        
        # Average monthly cost
        total_cost = sum(m.actual_cost_usd or m.estimated_cost_usd for m in history)
        avg_monthly = total_cost / 12
        
        return avg_monthly * months
    
    @classmethod
    def get_fleet_maintenance_forecast(cls, months=6):
        """Get maintenance forecast for entire fleet"""
        forecast = []
        
        for aircraft in Aircraft.objects.filter(is_active=True):
            next_due = cls.predict_next_maintenance(aircraft)
            if next_due and next_due <= timezone.now() + timedelta(days=30 * months):
                forecast.append({
                    'aircraft': aircraft.registration_number,
                    'model': aircraft.model,
                    'predicted_date': next_due,
                    'estimated_cost': cls.predict_maintenance_cost(aircraft, 1),
                    'priority': cls.calculate_priority(aircraft, next_due)
                })
        
        return sorted(forecast, key=lambda x: x['predicted_date'])
    
    @classmethod
    def calculate_priority(cls, aircraft, due_date):
        """Calculate maintenance priority"""
        days_until = (due_date - timezone.now()).days
        
        if days_until < 7:
            return 'critical'
        elif days_until < 30:
            return 'high'
        elif days_until < 90:
            return 'medium'
        else:
            return 'low'