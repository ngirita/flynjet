from django.db import models
from django.utils import timezone
from datetime import timedelta
from apps.accounts.models import User
from .models import Aircraft
import logging

logger = logging.getLogger(__name__)

class CrewMember(models.Model):
    """Crew member information"""
    
    CREW_ROLES = (
        ('captain', 'Captain'),
        ('first_officer', 'First Officer'),
        ('flight_engineer', 'Flight Engineer'),
        ('cabin_crew', 'Cabin Crew'),
        ('technician', 'Technician'),
    )
    
    CERTIFICATION_STATUS = (
        ('active', 'Active'),
        ('expiring', 'Expiring Soon'),
        ('expired', 'Expired'),
        ('suspended', 'Suspended'),
    )
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='crew_profile')
    employee_id = models.CharField(max_length=50, unique=True)
    
    # Personal Info
    date_of_birth = models.DateField()
    nationality = models.CharField(max_length=100)
    
    # Professional Info
    role = models.CharField(max_length=20, choices=CREW_ROLES)
    qualifications = models.JSONField(default=list)
    years_experience = models.IntegerField(default=0)
    
    # Certifications
    license_number = models.CharField(max_length=100)
    license_issued = models.DateField()
    license_expiry = models.DateField()
    certification_status = models.CharField(max_length=20, choices=CERTIFICATION_STATUS, default='active')
    
    # Medical
    medical_certificate = models.CharField(max_length=100)
    medical_expiry = models.DateField()
    
    # Aircraft Qualifications
    qualified_aircraft = models.ManyToManyField(Aircraft, related_name='qualified_crew', blank=True)
    
    # Employment
    date_hired = models.DateField()
    is_active = models.BooleanField(default=True)
    
    # Contact
    emergency_contact_name = models.CharField(max_length=200)
    emergency_contact_phone = models.CharField(max_length=20)
    emergency_contact_relation = models.CharField(max_length=100)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['employee_id']
    
    def __str__(self):
        return f"{self.get_role_display()}: {self.user.get_full_name()} ({self.employee_id})"
    
    def check_certifications(self):
        """Check if certifications are current"""
        today = timezone.now().date()
        
        # Check license expiry
        days_until_expiry = (self.license_expiry - today).days
        if days_until_expiry <= 0:
            self.certification_status = 'expired'
        elif days_until_expiry <= 30:
            self.certification_status = 'expiring'
        else:
            self.certification_status = 'active'
        
        self.save(update_fields=['certification_status'])
        return self.certification_status
    
    def add_qualification(self, aircraft_id):
        """Add aircraft qualification"""
        aircraft = Aircraft.objects.get(id=aircraft_id)
        self.qualified_aircraft.add(aircraft)
        logger.info(f"Added {aircraft} qualification to {self.user.email}")
    
    def remove_qualification(self, aircraft_id):
        """Remove aircraft qualification"""
        aircraft = Aircraft.objects.get(id=aircraft_id)
        self.qualified_aircraft.remove(aircraft)
        logger.info(f"Removed {aircraft} qualification from {self.user.email}")

class CrewSchedule(models.Model):
    """Crew duty schedule"""
    
    SCHEDULE_STATUS = (
        ('scheduled', 'Scheduled'),
        ('confirmed', 'Confirmed'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    )
    
    crew = models.ForeignKey(CrewMember, on_delete=models.CASCADE, related_name='schedules')
    flight_number = models.CharField(max_length=20)
    
    # Duty times
    duty_start = models.DateTimeField()
    duty_end = models.DateTimeField()
    briefing_time = models.DateTimeField(null=True, blank=True)
    
    # Flight details
    departure_airport = models.CharField(max_length=3)
    arrival_airport = models.CharField(max_length=3)
    
    # Status
    status = models.CharField(max_length=20, choices=SCHEDULE_STATUS, default='scheduled')
    is_standby = models.BooleanField(default=False)
    
    # Notes
    notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['duty_start']
        indexes = [
            models.Index(fields=['crew', 'duty_start']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"{self.crew} - {self.flight_number} ({self.duty_start.date()})"
    
    @property
    def duty_duration(self):
        """Calculate duty duration in hours"""
        duration = self.duty_end - self.duty_start
        return duration.total_seconds() / 3600

class CrewAvailability(models.Model):
    """Crew availability tracking"""
    
    crew = models.ForeignKey(CrewMember, on_delete=models.CASCADE, related_name='availability')
    date = models.DateField()
    
    # Time slots (24-hour format)
    time_slots = models.JSONField(default=list)  # List of available time ranges
    
    is_available = models.BooleanField(default=True)
    reason = models.CharField(max_length=200, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['crew', 'date']
        ordering = ['date']
    
    def __str__(self):
        return f"{self.crew} - {self.date}: {'Available' if self.is_available else 'Unavailable'}"

class CrewLeave(models.Model):
    """Crew leave requests"""
    
    LEAVE_TYPES = (
        ('annual', 'Annual Leave'),
        ('sick', 'Sick Leave'),
        ('training', 'Training'),
        ('personal', 'Personal Leave'),
    )
    
    LEAVE_STATUS = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
    )
    
    crew = models.ForeignKey(CrewMember, on_delete=models.CASCADE, related_name='leaves')
    leave_type = models.CharField(max_length=20, choices=LEAVE_TYPES)
    
    start_date = models.DateField()
    end_date = models.DateField()
    days_requested = models.IntegerField()
    
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=LEAVE_STATUS, default='pending')
    
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_leaves')
    approved_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.crew} - {self.get_leave_type_display()} ({self.start_date} to {self.end_date})"
    
    def approve(self, approver):
        """Approve leave request"""
        self.status = 'approved'
        self.approved_by = approver
        self.approved_at = timezone.now()
        self.save(update_fields=['status', 'approved_by', 'approved_at'])
        
        # Update availability
        current_date = self.start_date
        while current_date <= self.end_date:
            CrewAvailability.objects.update_or_create(
                crew=self.crew,
                date=current_date,
                defaults={
                    'is_available': False,
                    'reason': f"{self.get_leave_type_display()}: {self.reason[:50]}"
                }
            )
            current_date += timedelta(days=1)
        
        logger.info(f"Leave approved for {self.crew} by {approver.email}")
    
    def reject(self, approver, reason):
        """Reject leave request"""
        self.status = 'rejected'
        self.approved_by = approver
        self.approved_at = timezone.now()
        self.save(update_fields=['status', 'approved_by', 'approved_at'])
        
        logger.info(f"Leave rejected for {self.crew} by {approver.email}: {reason}")

class CrewManager:
    """Manage crew operations"""
    
    @classmethod
    def find_available_crew(cls, date, role=None, hours_needed=8):
        """Find available crew for given date"""
        available = CrewMember.objects.filter(
            is_active=True,
            availability__date=date,
            availability__is_available=True
        )
        
        if role:
            available = available.filter(role=role)
        
        # Exclude crew on leave
        on_leave = CrewLeave.objects.filter(
            status='approved',
            start_date__lte=date,
            end_date__gte=date
        ).values_list('crew_id', flat=True)
        
        available = available.exclude(id__in=on_leave)
        
        return available
    
    @classmethod
    def check_duty_time_limits(cls, crew, proposed_duty_start, proposed_duty_end):
        """Check if duty time limits are respected"""
        # Get duty in last 24 hours
        last_24h_start = proposed_duty_start - timedelta(hours=24)
        recent_duties = CrewSchedule.objects.filter(
            crew=crew,
            duty_start__gte=last_24h_start,
            status__in=['scheduled', 'confirmed', 'completed']
        )
        
        # Calculate total duty in last 24h
        total_duty_hours = 0
        for duty in recent_duties:
            duration = (duty.duty_end - duty.duty_start).total_seconds() / 3600
            total_duty_hours += duration
        
        # Calculate proposed duty duration
        proposed_duration = (proposed_duty_end - proposed_duty_start).total_seconds() / 3600
        
        # Check limits (simplified - real regulations are more complex)
        if total_duty_hours + proposed_duration > 14:  # Max 14 hours duty in 24h
            return False, "Would exceed 14-hour duty limit in 24-hour period"
        
        # Check minimum rest period (8 hours)
        last_duty = recent_duties.order_by('-duty_end').first()
        if last_duty:
            rest_period = (proposed_duty_start - last_duty.duty_end).total_seconds() / 3600
            if rest_period < 8:
                return False, f"Minimum 8-hour rest period required. Only {rest_period:.1f} hours available"
        
        return True, "Duty time OK"
    
    @classmethod
    def generate_crew_report(cls, crew_id, start_date, end_date):
        """Generate crew activity report"""
        crew = CrewMember.objects.get(id=crew_id)
        
        schedules = CrewSchedule.objects.filter(
            crew=crew,
            duty_start__date__gte=start_date,
            duty_start__date__lte=end_date
        ).order_by('duty_start')
        
        leaves = CrewLeave.objects.filter(
            crew=crew,
            start_date__lte=end_date,
            end_date__gte=start_date
        )
        
        total_duty_hours = 0
        flights_count = 0
        
        for schedule in schedules:
            duration = (schedule.duty_end - schedule.duty_start).total_seconds() / 3600
            total_duty_hours += duration
            flights_count += 1
        
        return {
            'crew': f"{crew.user.get_full_name()} ({crew.employee_id})",
            'role': crew.get_role_display(),
            'period': f"{start_date} to {end_date}",
            'total_duty_hours': total_duty_hours,
            'flights_assigned': flights_count,
            'leave_days': leaves.count(),
            'schedules': list(schedules.values()),
            'leaves': list(leaves.values())
        }