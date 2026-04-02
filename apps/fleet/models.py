import uuid
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from imagekit.models import ProcessedImageField
from imagekit.processors import ResizeToFill, SmartResize
from apps.core.models import TimeStampedModel
from django.db.models.signals import post_save
from django.dispatch import receiver


class AircraftCategory(models.Model):
    """Categories of aircraft - Only 3 types"""
    
    CATEGORY_TYPES = (
        ('private_jet', 'Private Jet'),
        ('cargo', 'Cargo Plane'),
        ('helicopter', 'Helicopter'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    category_type = models.CharField(max_length=20, choices=CATEGORY_TYPES, unique=True)
    description = models.TextField(blank=True)
    icon = models.ImageField(upload_to='category_icons/', blank=True)
    image = ProcessedImageField(
        upload_to='category_images/',
        processors=[ResizeToFill(800, 600)],
        format='JPEG',
        options={'quality': 90},
        blank=True,
        null=True
    )
    sort_order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name_plural = "Aircraft Categories"
        ordering = ['sort_order', 'name']
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        # Auto-set name and slug based on category_type
        if not self.name:
            self.name = dict(self.CATEGORY_TYPES).get(self.category_type, '')
        if not self.slug:
            self.slug = self.category_type
        super().save(*args, **kwargs)


class AircraftManufacturer(models.Model):
    """Aircraft manufacturers (Boeing, Airbus, etc.)"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True)
    logo = models.ImageField(upload_to='manufacturer_logos/', blank=True)
    country = models.CharField(max_length=100)
    website = models.URLField(blank=True)
    description = models.TextField(blank=True)
    founded_year = models.IntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return self.name


class AircraftStatusHistory(models.Model):
    """Track aircraft status changes"""
    
    aircraft = models.ForeignKey('Aircraft', on_delete=models.CASCADE, related_name='status_history')
    old_status = models.CharField(max_length=20)
    new_status = models.CharField(max_length=20)
    changed_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True)
    reason = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = "Aircraft status histories"
    
    def __str__(self):
        return f"{self.aircraft.registration_number}: {self.old_status} -> {self.new_status} at {self.created_at}"


# fleet/models.py - Update the Aircraft model

class Aircraft(models.Model):
    """Simplified Aircraft model with only essential fields"""
    
    AIRCRAFT_STATUS = (
        ('available', 'Available'),
        ('booked', 'Booked'),
        ('maintenance', 'Under Maintenance'),
        ('chartered', 'Chartered'),
        ('grounded', 'Grounded'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Basic Information
    registration_number = models.CharField(max_length=20, unique=True, db_index=True)
    manufacturer = models.ForeignKey(AircraftManufacturer, on_delete=models.PROTECT, related_name='aircraft')
    category = models.ForeignKey(AircraftCategory, on_delete=models.PROTECT, related_name='aircraft')
    model = models.CharField(max_length=100)
    variant = models.CharField(max_length=100, blank=True)
    year_of_manufacture = models.IntegerField()
    
    # Capacity
    passenger_capacity = models.IntegerField(
        validators=[MinValueValidator(0)], 
        help_text="Maximum number of passengers (0 for cargo aircraft)"
    )
    crew_required = models.IntegerField(default=2, help_text="Minimum crew required")
    cargo_capacity_kg = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True, 
        help_text="For cargo aircraft only"
    )
    baggage_capacity_kg = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, 
        help_text="Baggage capacity in kg"
    )
    
    # Performance (Essential)
    max_range_nm = models.IntegerField(help_text="Range in nautical miles")
    cruise_speed_knots = models.IntegerField(help_text="Cruising speed in knots")
    
    # Dimensions (Simplified)
    length_m = models.DecimalField(max_digits=5, decimal_places=2, help_text="Aircraft length in meters")
    wingspan_m = models.DecimalField(max_digits=5, decimal_places=2, help_text="Wingspan in meters")
    height_m = models.DecimalField(max_digits=5, decimal_places=2, help_text="Aircraft height in meters")
    cabin_height_m = models.DecimalField(max_digits=4, decimal_places=2, help_text="Cabin height in meters")
    cabin_width_m = models.DecimalField(max_digits=4, decimal_places=2, help_text="Cabin width in meters")
    cabin_length_m = models.DecimalField(max_digits=5, decimal_places=2, help_text="Cabin length in meters")
    
    # Amenities (Checkboxes - Quick selection)
    wifi_available = models.BooleanField(default=True)
    satellite_phone = models.BooleanField(default=False)
    entertainment_system = models.BooleanField(default=True)
    galley = models.BooleanField(default=True)
    lavatory = models.BooleanField(default=True)
    shower = models.BooleanField(default=False)
    bedroom = models.BooleanField(default=False)
    conference_table = models.BooleanField(default=False)
    
    # Status & Location
    status = models.CharField(max_length=20, choices=AIRCRAFT_STATUS, default='available', db_index=True)
    base_airport = models.CharField(max_length=3, help_text="IATA code of home base (e.g., JFK, LHR)")
    current_location = models.CharField(max_length=3, help_text="IATA code of current location (e.g., JFK, LHR)")
    
    # Images (Main image is thumbnail, others in AircraftImage model)
    thumbnail = ProcessedImageField(
        upload_to='aircraft/thumbnails/',
        processors=[SmartResize(600, 400)],
        format='JPEG',
        options={'quality': 85},
        blank=True,
        null=True,
        help_text="Main display image for this aircraft"
    )
    
    # Operational (Basic tracking)
    total_flight_hours = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    average_rating = models.FloatField(default=0.0, verbose_name="Average Rating")
    review_count = models.IntegerField(default=0, verbose_name="Number of Reviews")
    
    # NO PRICING FIELDS - Removed hourly_rate_usd, daily_rate_usd, etc.
    
    # Metadata
    is_active = models.BooleanField(default=True, db_index=True)
    is_featured = models.BooleanField(default=False)
    notes = models.TextField(blank=True, help_text="Additional notes or special features")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['manufacturer__name', 'model']
        indexes = [
            models.Index(fields=['registration_number']),
            models.Index(fields=['status', 'base_airport']),
            models.Index(fields=['category', 'status']),
            models.Index(fields=['passenger_capacity']),
        ]
    
    def __str__(self):
        return f"{self.manufacturer.name} {self.model} - {self.registration_number}"
    
    @property
    def age(self):
        return timezone.now().year - self.year_of_manufacture
    
    @property
    def is_available(self):
        return self.status == 'available'
    
    def update_status(self, new_status, user=None):
        """Update aircraft status and log the change"""
        old_status = self.status
        self.status = new_status
        self.save(update_fields=['status', 'updated_at'])
        
        AircraftStatusHistory.objects.create(
            aircraft=self,
            old_status=old_status,
            new_status=new_status,
            changed_by=user
        )
    
    def record_flight(self, hours):
        """Record flight hours"""
        self.total_flight_hours += hours
        self.save(update_fields=['total_flight_hours', 'last_flight_date'])


class AircraftImage(models.Model):
    """Multiple images for aircraft - Viewable by clients"""
    
    aircraft = models.ForeignKey(Aircraft, on_delete=models.CASCADE, related_name='images')
    image = ProcessedImageField(
        upload_to='aircraft/images/',
        processors=[ResizeToFill(1920, 1080)],
        format='JPEG',
        options={'quality': 90}
    )
    thumbnail = ProcessedImageField(
        upload_to='aircraft/thumbnails/',
        processors=[SmartResize(400, 300)],
        format='JPEG',
        options={'quality': 85},
        null=True,
        blank=True
    )
    caption = models.CharField(max_length=200, blank=True, help_text="Brief description of the image")
    is_primary = models.BooleanField(default=False, help_text="Set as main image for gallery")
    sort_order = models.IntegerField(default=0, help_text="Order in which images appear")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['sort_order', 'created_at']
    
    def __str__(self):
        return f"Image for {self.aircraft.registration_number}"
    
    def save(self, *args, **kwargs):
        if self.is_primary:
            # Set all other images of this aircraft to not primary
            AircraftImage.objects.filter(aircraft=self.aircraft, is_primary=True).update(is_primary=False)
        super().save(*args, **kwargs)
    
    @property
    def image_url(self):
        if self.image:
            return self.image.url
        return None
    
    @property
    def thumbnail_url(self):
        if self.thumbnail:
            return self.thumbnail.url
        return self.image_url


class AircraftInterior360(models.Model):
    """360-degree interior views"""
    
    aircraft = models.ForeignKey(Aircraft, on_delete=models.CASCADE, related_name='interior_360')
    title = models.CharField(max_length=200)
    image = models.ImageField(upload_to='aircraft/360/')
    thumbnail = ProcessedImageField(
        upload_to='aircraft/360/thumbnails/',
        processors=[SmartResize(200, 150)],
        format='JPEG',
        options={'quality': 80}
    )
    sort_order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['sort_order']
        verbose_name = "360 Interior View"
        verbose_name_plural = "360 Interior Views"
    
    def __str__(self):
        return f"{self.title} - {self.aircraft.registration_number}"


class AircraftSpecification(models.Model):
    """Additional specifications for aircraft"""
    
    aircraft = models.ForeignKey(Aircraft, on_delete=models.CASCADE, related_name='specifications')
    name = models.CharField(max_length=100)
    value = models.CharField(max_length=200)
    unit = models.CharField(max_length=50, blank=True)
    icon = models.CharField(max_length=50, blank=True, help_text="Font Awesome icon class")
    sort_order = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['sort_order']
        unique_together = ['aircraft', 'name']
    
    def __str__(self):
        return f"{self.name}: {self.value} {self.unit}"


class AircraftAvailability(models.Model):
    """Aircraft availability schedule"""
    
    aircraft = models.ForeignKey(Aircraft, on_delete=models.CASCADE, related_name='availability')
    start_datetime = models.DateTimeField(db_index=True)
    end_datetime = models.DateTimeField(db_index=True)
    is_available = models.BooleanField(default=True)
    reason = models.CharField(max_length=200, blank=True, help_text="Reason if not available")
    booking = models.ForeignKey('bookings.Booking', on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name_plural = "Aircraft availabilities"
        indexes = [
            models.Index(fields=['aircraft', 'start_datetime', 'end_datetime']),
        ]
    
    def __str__(self):
        status = "Available" if self.is_available else "Not Available"
        return f"{self.aircraft.registration_number} - {status} from {self.start_datetime} to {self.end_datetime}"


class AircraftMaintenance(models.Model):
    """Aircraft maintenance records"""
    
    MAINTENANCE_TYPES = (
        ('scheduled', 'Scheduled Maintenance'),
        ('unscheduled', 'Unscheduled Repair'),
        ('inspection', 'Inspection'),
        ('overhaul', 'Overhaul'),
        ('modification', 'Modification'),
        ('certification', 'Certification Renewal'),
    )
    
    MAINTENANCE_STATUS = (
        ('scheduled', 'Scheduled'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('delayed', 'Delayed'),
    )
    
    aircraft = models.ForeignKey(Aircraft, on_delete=models.CASCADE, related_name='maintenance_records')
    maintenance_type = models.CharField(max_length=20, choices=MAINTENANCE_TYPES)
    status = models.CharField(max_length=20, choices=MAINTENANCE_STATUS, default='scheduled')
    title = models.CharField(max_length=200)
    description = models.TextField()
    
    # Schedule
    scheduled_start = models.DateTimeField()
    scheduled_end = models.DateTimeField()
    actual_start = models.DateTimeField(null=True, blank=True)
    actual_end = models.DateTimeField(null=True, blank=True)
    
    # Location
    maintenance_location = models.CharField(max_length=3, help_text="IATA code")
    maintenance_facility = models.CharField(max_length=200)
    
    # Costs
    estimated_cost_usd = models.DecimalField(max_digits=12, decimal_places=2)
    actual_cost_usd = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3, default='USD')
    
    # Personnel
    technician_name = models.CharField(max_length=200, blank=True)
    technician_license = models.CharField(max_length=100, blank=True)
    supervisor_name = models.CharField(max_length=200, blank=True)
    
    # Parts
    parts_used = models.JSONField(default=list, blank=True)
    
    # Documentation
    work_order_number = models.CharField(max_length=100, unique=True)
    report_document = models.FileField(upload_to='maintenance_reports/', blank=True)
    completion_certificate = models.FileField(upload_to='maintenance_certs/', blank=True)
    
    # Results
    findings = models.TextField(blank=True)
    recommendations = models.TextField(blank=True)
    next_maintenance_due = models.DateTimeField(null=True, blank=True)
    next_maintenance_type = models.CharField(max_length=100, blank=True)
    
    # Metadata
    created_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-scheduled_start']
        indexes = [
            models.Index(fields=['aircraft', 'status']),
            models.Index(fields=['scheduled_start', 'scheduled_end']),
        ]
    
    def __str__(self):
        return f"{self.aircraft.registration_number} - {self.title} ({self.get_status_display()})"
    
    def start_maintenance(self):
        """Start the maintenance"""
        self.status = 'in_progress'
        self.actual_start = timezone.now()
        self.save(update_fields=['status', 'actual_start'])
        
        # Update aircraft status
        self.aircraft.update_status('maintenance')
    
    def complete_maintenance(self, actual_cost=None):
        """Complete the maintenance"""
        self.status = 'completed'
        self.actual_end = timezone.now()
        self.completed_at = timezone.now()
        if actual_cost:
            self.actual_cost_usd = actual_cost
        self.save(update_fields=['status', 'actual_end', 'completed_at', 'actual_cost_usd'])
        
        # Update aircraft status back to available
        self.aircraft.update_status('available')
        
        # Update next maintenance due if provided
        if self.next_maintenance_due:
            self.aircraft.next_maintenance_due = self.next_maintenance_due
            self.aircraft.next_maintenance_type = self.next_maintenance_type
            self.aircraft.save(update_fields=['next_maintenance_due', 'next_maintenance_type'])


class AircraftDocument(models.Model):
    """Aircraft documents and certificates"""
    
    DOCUMENT_TYPES = (
        ('certificate', 'Certificate'),
        ('manual', 'Manual'),
        ('logbook', 'Logbook'),
        ('insurance', 'Insurance'),
        ('warranty', 'Warranty'),
        ('technical', 'Technical Document'),
        ('legal', 'Legal Document'),
    )
    
    aircraft = models.ForeignKey(Aircraft, on_delete=models.CASCADE, related_name='documents')
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPES)
    title = models.CharField(max_length=200)
    document_number = models.CharField(max_length=100, blank=True)
    file = models.FileField(upload_to='aircraft/documents/')
    issue_date = models.DateField()
    expiry_date = models.DateField(null=True, blank=True)
    issuing_authority = models.CharField(max_length=200, blank=True)
    is_approved = models.BooleanField(default=False)
    approved_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_documents')
    approved_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-issue_date']
        indexes = [
            models.Index(fields=['aircraft', 'document_type']),
            models.Index(fields=['expiry_date']),
        ]
    
    def __str__(self):
        return f"{self.aircraft.registration_number} - {self.title}"
    
    def is_expired(self):
        """Check if document is expired"""
        if self.expiry_date:
            return self.expiry_date < timezone.now().date()
        return False
    
    def days_until_expiry(self):
        """Get days until expiry"""
        if self.expiry_date:
            delta = self.expiry_date - timezone.now().date()
            return delta.days
        return None


class FleetStats(models.Model):
    """Fleet statistics and analytics"""
    
    date = models.DateField(db_index=True)
    total_aircraft = models.IntegerField()
    available_aircraft = models.IntegerField()
    in_maintenance = models.IntegerField()
    booked_aircraft = models.IntegerField()
    
    # Utilization
    total_flight_hours = models.DecimalField(max_digits=10, decimal_places=2)
    average_utilization_rate = models.DecimalField(max_digits=5, decimal_places=2, help_text="Percentage")
    
    # Revenue
    total_revenue_usd = models.DecimalField(max_digits=15, decimal_places=2)
    average_revenue_per_aircraft = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Maintenance
    scheduled_maintenance_count = models.IntegerField()
    completed_maintenance_count = models.IntegerField()
    maintenance_cost_usd = models.DecimalField(max_digits=15, decimal_places=2)
    
    # Categories breakdown
    category_breakdown = models.JSONField(default=dict)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name_plural = "Fleet statistics"
        unique_together = ['date']
        ordering = ['-date']
    
    def __str__(self):
        return f"Fleet Stats for {self.date}"


class Enquiry(models.Model):
    """Enquiry for aircraft charter"""
    
    ENQUIRY_STATUS = (
        ('new', 'New'),
        ('reviewed', 'Reviewed'),
        ('contract_sent', 'Contract Sent'),
        ('payment_received', 'Payment Received'),
        ('booked', 'Booked'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    enquiry_number = models.CharField(max_length=20, unique=True, db_index=True)
    
    # Contact Details
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    country = models.CharField(max_length=100, blank=True)
    
    # Flight Details
    aircraft = models.ForeignKey(Aircraft, on_delete=models.SET_NULL, null=True, blank=True, related_name='enquiries')
    aircraft_category = models.CharField(max_length=50, choices=AircraftCategory.CATEGORY_TYPES, blank=True)
    
    departure_airport = models.CharField(max_length=3, blank=True, help_text="IATA code")
    arrival_airport = models.CharField(max_length=3, blank=True, help_text="IATA code")
    preferred_departure_date = models.DateField(null=True, blank=True)
    preferred_return_date = models.DateField(null=True, blank=True)
    flexible_dates = models.BooleanField(default=False)
    
    # Passenger Details
    passenger_count = models.IntegerField(default=1)
    luggage_count = models.IntegerField(default=0)
    luggage_weight_kg = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Total luggage weight in kg")
    special_luggage = models.TextField(blank=True, help_text="Golf clubs, skis, etc.")
    
    # ADD THIS FIELD - Cargo Details
    cargo_weight_kg = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True, 
        help_text="Cargo weight in kg (for cargo enquiries)"
    )
    
    # Amenities & Requirements
    amenities = models.JSONField(default=list, blank=True, help_text="WiFi, catering, etc.")
    catering_requirements = models.TextField(blank=True)
    special_requests = models.TextField(blank=True)
    
    # Additional Services
    ground_transportation = models.BooleanField(default=False)
    hotel_accommodation = models.BooleanField(default=False)
    pet_travel = models.BooleanField(default=False)
    
    # Status Tracking
    status = models.CharField(max_length=20, choices=ENQUIRY_STATUS, default='new')
    notes = models.TextField(blank=True, help_text="Internal notes")
    
    # Admin Response
    contract_sent_at = models.DateTimeField(null=True, blank=True)
    contract_expiry = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    source = models.CharField(max_length=50, default='website')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['enquiry_number']),
            models.Index(fields=['email', 'status']),
            models.Index(fields=['status', 'created_at']),
        ]
    
    def __str__(self):
        return f"Enquiry {self.enquiry_number} - {self.first_name} {self.last_name}"
    
    def save(self, *args, **kwargs):
        if not self.enquiry_number:
            self.enquiry_number = self.generate_enquiry_number()
        super().save(*args, **kwargs)
    
    def generate_enquiry_number(self):
        """Generate unique enquiry number"""
        import random
        import string
        timestamp = timezone.now().strftime('%Y%m%d')
        random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        return f"ENQ{timestamp}{random_str}"
    
    def get_full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    @property
    def is_cargo(self):
        """Check if this is a cargo enquiry"""
        return bool(self.cargo_weight_kg) or (self.passenger_count == 0 and self.cargo_weight_kg)    

@receiver(post_save, sender=Enquiry)
def create_admin_notification_for_enquiry(sender, instance, created, **kwargs):
    """Create admin notification when new enquiry is created"""
    if created:
        from apps.core.models import AdminNotification
        
        aircraft_name = f"{instance.aircraft.manufacturer.name} {instance.aircraft.model}" if instance.aircraft else "Any Aircraft"
        
        AdminNotification.objects.create(
            notification_type='enquiry',
            title=f'New Enquiry: {instance.enquiry_number}',
            message=f'New enquiry from {instance.get_full_name()} for {aircraft_name}. Passengers: {instance.passenger_count}.',
            link=f'/admin/fleet/enquiry/{instance.id}/change/',
            is_read=False
        )