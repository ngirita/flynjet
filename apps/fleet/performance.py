from django.db import models
from django.utils import timezone
from datetime import timedelta
from django.db.models import Avg, Sum, Count
from .models import Aircraft, AircraftMaintenance
import logging

logger = logging.getLogger(__name__)

class FlightPerformance(models.Model):
    """Track flight performance metrics"""
    
    aircraft = models.ForeignKey(Aircraft, on_delete=models.CASCADE, related_name='performance_records')
    flight_date = models.DateTimeField()
    
    # Flight metrics
    flight_hours = models.DecimalField(max_digits=8, decimal_places=2)
    fuel_consumed = models.DecimalField(max_digits=10, decimal_places=2)  # in liters
    distance_nm = models.IntegerField()
    
    # Performance metrics
    avg_speed = models.IntegerField()  # knots
    max_altitude = models.IntegerField()  # feet
    fuel_efficiency = models.DecimalField(max_digits=8, decimal_places=2)  # nm per liter
    
    # Environmental
    co2_emissions = models.DecimalField(max_digits=10, decimal_places=2)  # kg
    
    # Crew
    captain = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, related_name='captain_flights')
    first_officer = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, related_name='fo_flights')
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-flight_date']
        indexes = [
            models.Index(fields=['aircraft', '-flight_date']),
        ]
    
    def __str__(self):
        return f"{self.aircraft.registration_number} - {self.flight_date}"
    
    def save(self, *args, **kwargs):
        # Calculate fuel efficiency
        if self.distance_nm > 0 and self.fuel_consumed > 0:
            self.fuel_efficiency = self.distance_nm / self.fuel_consumed
        super().save(*args, **kwargs)

class AircraftPerformance(models.Model):
    """Aggregated aircraft performance metrics"""
    
    aircraft = models.OneToOneField(Aircraft, on_delete=models.CASCADE, related_name='performance_summary')
    
    # Lifetime metrics
    total_flight_hours = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_flights = models.IntegerField(default=0)
    total_distance = models.IntegerField(default=0)  # nautical miles
    total_fuel_consumed = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Average metrics
    avg_flight_duration = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    avg_fuel_efficiency = models.DecimalField(max_digits=8, decimal_places=4, default=0)
    avg_speed = models.IntegerField(default=0)
    
    # Utilization
    utilization_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)  # percentage
    days_since_last_flight = models.IntegerField(default=0)
    
    # Reliability
    maintenance_incidents = models.IntegerField(default=0)
    unscheduled_maintenance = models.IntegerField(default=0)
    mean_time_between_failures = models.IntegerField(default=0, help_text="Hours between failures")
    
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Performance Summary - {self.aircraft.registration_number}"
    
    def update_metrics(self):
        """Update performance metrics"""
        flights = FlightPerformance.objects.filter(aircraft=self.aircraft)
        
        # Total metrics
        self.total_flights = flights.count()
        self.total_flight_hours = flights.aggregate(Sum('flight_hours'))['flight_hours__sum'] or 0
        self.total_distance = flights.aggregate(Sum('distance_nm'))['distance_nm__sum'] or 0
        self.total_fuel_consumed = flights.aggregate(Sum('fuel_consumed'))['fuel_consumed__sum'] or 0
        
        # Averages
        if self.total_flights > 0:
            self.avg_flight_duration = self.total_flight_hours / self.total_flights
            self.avg_speed = flights.aggregate(Avg('avg_speed'))['avg_speed__avg'] or 0
            self.avg_fuel_efficiency = flights.aggregate(Avg('fuel_efficiency'))['fuel_efficiency__avg'] or 0
        
        # Last flight
        last_flight = flights.order_by('-flight_date').first()
        if last_flight:
            self.days_since_last_flight = (timezone.now().date() - last_flight.flight_date.date()).days
        
        # Maintenance stats
        maintenance = AircraftMaintenance.objects.filter(aircraft=self.aircraft)
        self.maintenance_incidents = maintenance.count()
        self.unscheduled_maintenance = maintenance.filter(maintenance_type='unscheduled').count()
        
        # Calculate MTBF
        if self.maintenance_incidents > 0:
            self.mean_time_between_failures = self.total_flight_hours / self.maintenance_incidents
        
        self.save()

class FuelEfficiencyAnalysis(models.Model):
    """Fuel efficiency analysis"""
    
    aircraft = models.ForeignKey(Aircraft, on_delete=models.CASCADE, related_name='fuel_analyses')
    analysis_date = models.DateField(auto_now_add=True)
    
    # Efficiency metrics
    avg_efficiency = models.DecimalField(max_digits=8, decimal_places=4)
    best_efficiency = models.DecimalField(max_digits=8, decimal_places=4)
    worst_efficiency = models.DecimalField(max_digits=8, decimal_places=4)
    
    # Factors affecting efficiency
    altitude_impact = models.JSONField(default=dict)
    speed_impact = models.JSONField(default=dict)
    weather_impact = models.JSONField(default=dict)
    
    # Recommendations
    recommendations = models.JSONField(default=list)
    
    class Meta:
        ordering = ['-analysis_date']
    
    def __str__(self):
        return f"Fuel Analysis - {self.aircraft.registration_number} ({self.analysis_date})"

class PerformanceDashboard:
    """Generate performance dashboards"""
    
    @classmethod
    def get_fleet_performance(cls, days=30):
        """Get fleet-wide performance metrics"""
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        
        flights = FlightPerformance.objects.filter(
            flight_date__date__gte=start_date,
            flight_date__date__lte=end_date
        )
        
        return {
            'period': f"{start_date} to {end_date}",
            'total_flights': flights.count(),
            'total_hours': flights.aggregate(Sum('flight_hours'))['flight_hours__sum'] or 0,
            'total_distance': flights.aggregate(Sum('distance_nm'))['distance_nm__sum'] or 0,
            'avg_fuel_efficiency': flights.aggregate(Avg('fuel_efficiency'))['fuel_efficiency__avg'] or 0,
            'by_aircraft': flights.values('aircraft__registration_number').annotate(
                flights=Count('id'),
                hours=Sum('flight_hours'),
                distance=Sum('distance_nm')
            ).order_by('-hours')
        }
    
    @classmethod
    def get_aircraft_performance(cls, aircraft_id, months=12):
        """Get aircraft performance over time"""
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=30 * months)
        
        flights = FlightPerformance.objects.filter(
            aircraft_id=aircraft_id,
            flight_date__date__gte=start_date
        ).order_by('flight_date')
        
        # Monthly aggregation
        monthly = flights.extra(
            {'month': "date_trunc('month', flight_date)"}
        ).values('month').annotate(
            flights=Count('id'),
            hours=Sum('flight_hours'),
            avg_efficiency=Avg('fuel_efficiency')
        ).order_by('month')
        
        return {
            'total_flights': flights.count(),
            'total_hours': flights.aggregate(Sum('flight_hours'))['flight_hours__sum'] or 0,
            'monthly': list(monthly)
        }

class PerformanceOptimizer:
    """Optimize aircraft performance"""
    
    @classmethod
    def analyze_efficiency_trends(cls, aircraft_id, days=90):
        """Analyze fuel efficiency trends"""
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        flights = FlightPerformance.objects.filter(
            aircraft_id=aircraft_id,
            flight_date__gte=start_date
        ).order_by('flight_date')
        
        if not flights.exists():
            return None
        
        # Calculate moving average
        efficiencies = list(flights.values_list('fuel_efficiency', flat=True))
        window = min(10, len(efficiencies) // 3)
        
        moving_avg = []
        for i in range(len(efficiencies) - window + 1):
            avg = sum(efficiencies[i:i+window]) / window
            moving_avg.append(avg)
        
        # Detect trends
        trend = 'stable'
        if len(moving_avg) >= 2:
            if moving_avg[-1] > moving_avg[0] * 1.05:
                trend = 'improving'
            elif moving_avg[-1] < moving_avg[0] * 0.95:
                trend = 'declining'
        
        return {
            'aircraft_id': aircraft_id,
            'period_days': days,
            'average_efficiency': flights.aggregate(Avg('fuel_efficiency'))['fuel_efficiency__avg'],
            'trend': trend,
            'moving_average': moving_avg,
            'recommendations': cls.generate_recommendations(aircraft_id, trend)
        }
    
    @classmethod
    def generate_recommendations(cls, aircraft_id, trend):
        """Generate performance recommendations"""
        recommendations = []
        
        if trend == 'declining':
            recommendations.extend([
                "Schedule engine performance check",
                "Verify proper flight planning for optimal altitudes",
                "Check for increased drag (landing gear, flaps)",
                "Review pilot techniques for fuel efficiency"
            ])
        elif trend == 'improving':
            recommendations.extend([
                "Continue current practices",
                "Share successful techniques with other crews",
                "Monitor for consistent performance"
            ])
        
        # Add maintenance-based recommendations
        aircraft = Aircraft.objects.get(id=aircraft_id)
        if aircraft.age > 10:
            recommendations.append("Consider age-related performance degradation")
        
        return recommendations