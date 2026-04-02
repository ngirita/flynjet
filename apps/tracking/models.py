import uuid
from django.db import models
from django.db.models import JSONField
from django.utils import timezone
from django.conf import settings
from model_utils import FieldTracker
from apps.core.models import TimeStampedModel
from apps.bookings.models import Booking
import logging

logger = logging.getLogger(__name__)


# ============ DEFINE TrackingPosition FIRST ============
class TrackingPosition(models.Model):
    """Historical tracking positions"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    track = models.ForeignKey('FlightTrack', on_delete=models.CASCADE, related_name='position_history')
    
    # Position Data
    latitude = models.FloatField()
    longitude = models.FloatField()
    altitude = models.FloatField(null=True, blank=True)
    heading = models.FloatField(null=True, blank=True)
    speed = models.FloatField(null=True, blank=True)
    
    # Timestamp
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['track', 'timestamp']),
        ]
    
    def __str__(self):
        return f"Position for {self.track.flight_number} at {self.timestamp}"


# ============ FlightTrack Model ============
class FlightTrack(TimeStampedModel):
    """Real-time flight tracking data"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    booking = models.OneToOneField(Booking, on_delete=models.CASCADE, related_name='tracking')
    
    # Flight Information
    flight_number = models.CharField(max_length=20, db_index=True)
    aircraft_registration = models.CharField(max_length=20)
    airline = models.CharField(max_length=100, blank=True)
    
    # Current Position
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    altitude = models.FloatField(null=True, blank=True, help_text="Altitude in feet")
    heading = models.FloatField(null=True, blank=True, help_text="Heading in degrees")
    speed = models.FloatField(null=True, blank=True, help_text="Ground speed in knots")
    vertical_speed = models.FloatField(null=True, blank=True, help_text="Vertical speed in feet/min")
    
    # Tracking Status
    is_tracking = models.BooleanField(default=True)
    last_update = models.DateTimeField(null=True, blank=True)
    next_update_expected = models.DateTimeField(null=True, blank=True)
    
    # Flight Status (NEW)
    FLIGHT_STATUS = (
        ('scheduled', 'Scheduled'),
        ('boarding', 'Boarding'),
        ('departed', 'Departed'),
        ('in_air', 'In Air'),
        ('en_route', 'En Route'),
        ('arrived', 'Arrived'),
        ('delayed', 'Delayed'),
        ('cancelled', 'Cancelled'),
        ('diverted', 'Diverted'),
        ('landed', 'Landed'),
    )
    status = models.CharField(max_length=20, choices=FLIGHT_STATUS, default='scheduled')
    
    # Actual Times (NEW)
    actual_departure = models.DateTimeField(null=True, blank=True)
    actual_arrival = models.DateTimeField(null=True, blank=True)
    delay_minutes = models.IntegerField(default=0)
    remarks = models.TextField(blank=True)
    
    # Cargo Tracking Fields (NEW)
    CARGO_STATUS = (
        ('pending', 'Pending'),
        ('loaded', 'Loaded'),
        ('in_transit', 'In Transit'),
        ('unloaded', 'Unloaded'),
        ('delivered', 'Delivered'),
    )
    cargo_status = models.CharField(max_length=20, choices=CARGO_STATUS, default='pending')
    cargo_manifest = models.JSONField(default=list, blank=True)
    cargo_weight = models.FloatField(null=True, blank=True, help_text="Weight in kg")
    
    # Flight Progress
    departure_time = models.DateTimeField()
    arrival_time = models.DateTimeField()
    estimated_arrival = models.DateTimeField(null=True, blank=True)
    progress_percentage = models.IntegerField(default=0)
    distance_remaining = models.FloatField(null=True, blank=True, help_text="Distance in nautical miles")
    time_remaining = models.DurationField(null=True, blank=True)
    
    # Route Information
    departure_airport = models.CharField(max_length=3)
    arrival_airport = models.CharField(max_length=3)
    departure_airport_name = models.CharField(max_length=100, blank=True)
    arrival_airport_name = models.CharField(max_length=100, blank=True)
    route = models.JSONField(default=list, blank=True, help_text="List of waypoints")
    alternate_airports = models.JSONField(default=list, blank=True)
    
    # Weather Data
    weather = models.JSONField(default=dict, blank=True)
    
    # Shareable Tracking Link
    share_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    share_expiry = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    data_source = models.CharField(max_length=50, default='manual', choices=[
        ('manual', 'Manual Input'),
        ('adsb', 'ADS-B'),
        ('flightradar', 'FlightRadar24'),
        ('gps', 'GPS Device'),
        ('api', 'External API'),
        ('simulated', 'Simulated'),
    ])
    raw_data = models.JSONField(default=dict, blank=True)
    
    # Add tracker for change detection (UPDATED to include status)
    tracker = FieldTracker(fields=['latitude', 'longitude', 'altitude', 'heading', 'speed', 'progress_percentage', 'status'])
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['flight_number']),
            models.Index(fields=['booking', 'is_tracking']),
            models.Index(fields=['last_update']),
            models.Index(fields=['share_token']),
            models.Index(fields=['status']),  # NEW
            models.Index(fields=['cargo_status']),  # NEW
        ]
    
    def __str__(self):
        return f"Flight {self.flight_number} - {self.booking.booking_reference}"
    
    def update_position(self, latitude, longitude, altitude=None, heading=None, speed=None):
        """Update current position"""
        self.latitude = latitude
        self.longitude = longitude
        self.altitude = altitude or self.altitude
        self.heading = heading or self.heading
        self.speed = speed or self.speed
        self.last_update = timezone.now()
        
        # Auto-update status based on position and time (NEW)
        self.update_status_from_position()
        
        # Calculate progress
        self.calculate_progress()
        
        # Calculate ETA
        self.calculate_eta()
        
        self.save(update_fields=[
            'latitude', 'longitude', 'altitude', 'heading', 'speed',
            'last_update', 'progress_percentage', 'distance_remaining',
            'time_remaining', 'estimated_arrival', 'status'  # Added status
        ])
        
        # Create position history - TrackingPosition is now defined above
        TrackingPosition.objects.create(
            track=self,
            latitude=latitude,
            longitude=longitude,
            altitude=altitude,
            heading=heading,
            speed=speed
        )
        
        logger.info(f"Flight {self.flight_number} position updated: {latitude}, {longitude}")
    
    def update_status_from_position(self):
        """Auto-update flight status based on current position and time (NEW)"""
        current_time = timezone.now()
        
        # If flight hasn't departed yet
        if not self.actual_departure and current_time >= self.departure_time:
            self.status = 'departed'
            self.actual_departure = current_time
        
        # If flight has departed and we have position data
        elif self.actual_departure and self.latitude and self.longitude:
            # Check if landed/arrived
            if self.actual_arrival or (current_time >= self.arrival_time):
                self.status = 'arrived'
                if not self.actual_arrival:
                    self.actual_arrival = current_time
            else:
                # In air or en route
                if self.altitude and self.altitude > 1000:  # Above 1000ft
                    self.status = 'in_air'
                else:
                    self.status = 'en_route'
        
        # Check for delays
        if not self.actual_departure and current_time > self.departure_time:
            self.status = 'delayed'
            self.delay_minutes = int((current_time - self.departure_time).total_seconds() / 60)
    
    def update_cargo_status(self, new_status, manifest_update=None, weight=None):
        """Update cargo tracking status (NEW)"""
        valid_statuses = dict(self.CARGO_STATUS).keys()
        if new_status not in valid_statuses:
            raise ValueError(f"Invalid cargo status. Must be one of: {', '.join(valid_statuses)}")
        
        self.cargo_status = new_status
        if manifest_update:
            self.cargo_manifest = manifest_update
        if weight is not None:
            self.cargo_weight = weight
        
        self.save(update_fields=['cargo_status', 'cargo_manifest', 'cargo_weight'])
        logger.info(f"Cargo status for {self.flight_number} updated to {new_status}")
    
    def calculate_progress(self):
        """Calculate flight progress percentage"""
        if not self.latitude or not self.longitude:
            return
        
        total_distance = self.calculate_total_distance()
        if total_distance and self.distance_remaining is not None:
            distance_covered = total_distance - self.distance_remaining
            self.progress_percentage = int((distance_covered / total_distance) * 100)
            self.progress_percentage = max(0, min(100, self.progress_percentage))
    
    def calculate_eta(self):
        """Calculate estimated arrival time"""
        if self.speed and self.distance_remaining and self.speed > 0:
            hours_remaining = self.distance_remaining / self.speed
            self.time_remaining = timezone.timedelta(hours=hours_remaining)
            self.estimated_arrival = timezone.now() + self.time_remaining
    
    def calculate_total_distance(self):
        """Calculate total flight distance using Haversine formula"""
        from .utils import calculate_distance
        
        # Airport coordinate database
        airport_coords = {
            'JFK': {'lat': 40.6413, 'lng': -73.7781},
            'LAX': {'lat': 33.9416, 'lng': -118.4085},
            'LHR': {'lat': 51.4700, 'lng': -0.4543},
            'CDG': {'lat': 49.0097, 'lng': 2.5479},
            'DXB': {'lat': 25.2532, 'lng': 55.3657},
            'HKG': {'lat': 22.3080, 'lng': 113.9185},
            'SYD': {'lat': -33.9399, 'lng': 151.1753},
            'FRA': {'lat': 50.0379, 'lng': 8.5622},
            'AMS': {'lat': 52.3081, 'lng': 4.7642},
            'SFO': {'lat': 37.6188, 'lng': -122.3750},
            'EWR': {'lat': 40.6925, 'lng': -74.1687},
            'ORD': {'lat': 41.9742, 'lng': -87.9073},
            'DFW': {'lat': 32.8998, 'lng': -97.0403},
            'DEN': {'lat': 39.8561, 'lng': -104.6737},
            'SEA': {'lat': 47.4502, 'lng': -122.3088},
            'MIA': {'lat': 25.7959, 'lng': -80.2870},
            'BOS': {'lat': 42.3656, 'lng': -71.0096},
            'IAD': {'lat': 38.9445, 'lng': -77.4558},
        }
        
        dep_coords = airport_coords.get(self.departure_airport, {'lat': 0, 'lng': 0})
        arr_coords = airport_coords.get(self.arrival_airport, {'lat': 0, 'lng': 0})
        
        if dep_coords['lat'] == 0 or arr_coords['lat'] == 0:
            return 1000  # Default fallback
            
        return calculate_distance(dep_coords['lat'], dep_coords['lng'], 
                                  arr_coords['lat'], arr_coords['lng'])
    
    def get_shareable_link(self):
        """Get shareable tracking link"""
        return f"/tracking/share/{self.share_token}/"
    
    def is_shareable(self):
        """Check if tracking link is still valid"""
        if self.share_expiry:
            return timezone.now() < self.share_expiry
        return True
    
    def generate_share_token(self, expiry_hours=24):
        """Generate new share token with expiry"""
        import uuid
        self.share_token = uuid.uuid4()
        self.share_expiry = timezone.now() + timezone.timedelta(hours=expiry_hours)
        self.save(update_fields=['share_token', 'share_expiry'])
        return self.share_token


# ============ TrackingNotification Model ============
class TrackingNotification(models.Model):
    """Notifications for tracking updates"""
    
    NOTIFICATION_TYPES = (
        ('departure', 'Flight Departed'),
        ('arrival', 'Flight Arrived'),
        ('delay', 'Flight Delayed'),
        ('position', 'Position Update'),
        ('weather', 'Weather Alert'),
        ('altitude', 'Altitude Change'),
        ('speed', 'Speed Change'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    track = models.ForeignKey(FlightTrack, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    
    # Notification Content
    title = models.CharField(max_length=200)
    message = models.TextField()
    data = models.JSONField(default=dict, blank=True)
    
    # Delivery Status
    is_sent = models.BooleanField(default=False)
    sent_at = models.DateTimeField(null=True, blank=True)
    
    # Recipients
    send_email = models.BooleanField(default=False)
    send_push = models.BooleanField(default=False)
    send_sms = models.BooleanField(default=False)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.get_notification_type_display()} for {self.track.flight_number}"
    
    def send(self):
        """Send the notification"""
        from django.core.mail import send_mail
        
        if self.send_email and self.track.booking.user.email:
            send_mail(
                self.title,
                self.message,
                settings.DEFAULT_FROM_EMAIL,
                [self.track.booking.user.email],
                fail_silently=True,
            )
        
        # Push notification would go here
        # SMS notification would go here
        
        self.is_sent = True
        self.sent_at = timezone.now()
        self.save(update_fields=['is_sent', 'sent_at'])


# ============ TrackingShare Model ============
class TrackingShare(models.Model):
    """Shared tracking links"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    track = models.ForeignKey(FlightTrack, on_delete=models.CASCADE, related_name='shares')
    
    # Share Details
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True)
    
    # Access Control
    password = models.CharField(max_length=128, blank=True)
    expires_at = models.DateTimeField()
    max_views = models.IntegerField(default=0, help_text="0 for unlimited")
    
    # Tracking
    views = models.IntegerField(default=0)
    last_viewed = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['token']),
            models.Index(fields=['expires_at']),
        ]
    
    def __str__(self):
        return f"Share for {self.track.flight_number}"
    
    def record_view(self):
        """Record a view of this share"""
        self.views += 1
        self.last_viewed = timezone.now()
        self.save(update_fields=['views', 'last_viewed'])
    
    def is_valid(self):
        """Check if share is still valid"""
        if self.expires_at and timezone.now() > self.expires_at:
            return False
        if self.max_views > 0 and self.views >= self.max_views:
            return False
        return True
    
    def check_password(self, password):
        """Check if password is correct"""
        if not self.password:
            return True
        from django.contrib.auth.hashers import check_password
        return check_password(password, self.password)


# ============ FlightAlert Model ============
class FlightAlert(models.Model):
    """Custom alerts for flights"""
    
    ALERT_TYPES = (
        ('takeoff', 'Takeoff'),
        ('landing', 'Landing'),
        ('waypoint', 'Waypoint Passed'),
        ('altitude', 'Altitude Change'),
        ('speed', 'Speed Change'),
        ('delay', 'Delay'),
        ('custom', 'Custom'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    track = models.ForeignKey(FlightTrack, on_delete=models.CASCADE, related_name='alerts')
    user = models.ForeignKey('accounts.User', on_delete=models.CASCADE, related_name='flight_alerts')
    
    # Alert Configuration
    alert_type = models.CharField(max_length=20, choices=ALERT_TYPES)
    threshold_value = models.FloatField(null=True, blank=True)
    custom_message = models.CharField(max_length=200, blank=True)
    
    # Notification Methods
    notify_email = models.BooleanField(default=True)
    notify_push = models.BooleanField(default=False)
    notify_sms = models.BooleanField(default=False)
    
    # Status
    is_active = models.BooleanField(default=True)
    last_triggered = models.DateTimeField(null=True, blank=True)
    trigger_count = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['track', 'user', 'alert_type']
    
    def __str__(self):
        return f"{self.get_alert_type_display()} alert for {self.track.flight_number}"
    
    def trigger(self, value=None):
        """Trigger the alert"""
        from django.core.mail import send_mail
        
        message = self.custom_message or f"Alert: {self.get_alert_type_display()} for flight {self.track.flight_number}"
        
        if self.notify_email:
            send_mail(
                f"Flight Alert - {self.track.flight_number}",
                message,
                settings.DEFAULT_FROM_EMAIL,
                [self.user.email],
                fail_silently=True,
            )
        
        self.last_triggered = timezone.now()
        self.trigger_count += 1
        self.save(update_fields=['last_triggered', 'trigger_count'])