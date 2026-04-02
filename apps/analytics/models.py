import uuid
from django.db import models
from django.utils import timezone
from django.contrib.postgres.fields import JSONField
from apps.core.models import TimeStampedModel
from apps.accounts.models import User
from apps.bookings.models import Booking
from apps.fleet.models import Aircraft

class AnalyticsEvent(models.Model):
    """Track user events for analytics"""
    
    EVENT_TYPES = (
        ('page_view', 'Page View'),
        ('booking_start', 'Booking Started'),
        ('booking_complete', 'Booking Completed'),
        ('payment_start', 'Payment Started'),
        ('payment_complete', 'Payment Completed'),
        ('search', 'Search Performed'),
        ('login', 'User Login'),
        ('signup', 'User Signup'),
        ('logout', 'User Logout'),
        ('document_download', 'Document Download'),
        ('chat_start', 'Chat Started'),
        ('chat_complete', 'Chat Completed'),
        ('review_submit', 'Review Submitted'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event_id = models.CharField(max_length=100, unique=True)
    
    # Event Info
    event_type = models.CharField(max_length=50, choices=EVENT_TYPES)
    timestamp = models.DateTimeField(db_index=True)
    
    # User (if authenticated)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    anonymous_id = models.CharField(max_length=100, blank=True)
    
    # Session
    session_id = models.CharField(max_length=100, db_index=True)
    
    # Page/URL
    url = models.URLField(max_length=500)
    referrer = models.URLField(max_length=500, blank=True)
    
    # Device Info
    user_agent = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    device_type = models.CharField(max_length=50, blank=True)
    browser = models.CharField(max_length=100, blank=True)
    os = models.CharField(max_length=100, blank=True)
    
    # Location
    country = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)
    
    # Event Data
    data = models.JSONField(default=dict, blank=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['event_id']),
            models.Index(fields=['event_type', 'timestamp']),
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['session_id']),
        ]
    
    def __str__(self):
        return f"{self.event_type} at {self.timestamp}"


class DailyMetric(models.Model):
    """Daily aggregated metrics"""
    
    date = models.DateField(unique=True, db_index=True)
    
    # User Metrics
    new_users = models.IntegerField(default=0)
    active_users = models.IntegerField(default=0)
    returning_users = models.IntegerField(default=0)
    
    # Booking Metrics
    total_bookings = models.IntegerField(default=0)
    completed_bookings = models.IntegerField(default=0)
    cancelled_bookings = models.IntegerField(default=0)
    booking_value = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    average_booking_value = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Revenue Metrics
    revenue = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    refunds = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    net_revenue = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Payment Metrics
    payment_success = models.IntegerField(default=0)
    payment_failed = models.IntegerField(default=0)
    payment_method_breakdown = models.JSONField(default=dict)
    
    # Fleet Metrics
    flights_completed = models.IntegerField(default=0)
    flight_hours = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    fleet_utilization = models.FloatField(default=0)
    
    # Traffic Metrics
    page_views = models.IntegerField(default=0)
    unique_visitors = models.IntegerField(default=0)
    bounce_rate = models.FloatField(default=0)
    avg_session_duration = models.IntegerField(default=0)
    
    # Support Metrics
    support_tickets = models.IntegerField(default=0)
    avg_response_time = models.IntegerField(default=0)
    satisfaction_score = models.FloatField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-date']
    
    def __str__(self):
        return f"Daily Metrics for {self.date}"


class Report(TimeStampedModel):
    """Saved reports"""
    
    REPORT_TYPES = (
        ('revenue', 'Revenue Report'),
        ('bookings', 'Bookings Report'),
        ('fleet', 'Fleet Utilization'),
        ('customer', 'Customer Analytics'),
        ('payment', 'Payment Analysis'),
        ('support', 'Support Performance'),
        ('marketing', 'Marketing ROI'),
        ('custom', 'Custom Report'),
    )
    
    FORMATS = (
        ('pdf', 'PDF'),
        ('excel', 'Excel'),
        ('csv', 'CSV'),
        ('json', 'JSON'),
    )
    
    FREQUENCIES = (
        ('one_time', 'One Time'),
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    report_number = models.CharField(max_length=50, unique=True)
    
    # Basic Info
    name = models.CharField(max_length=200)
    report_type = models.CharField(max_length=20, choices=REPORT_TYPES)
    description = models.TextField(blank=True)
    
    # Configuration
    parameters = models.JSONField(default=dict)
    format = models.CharField(max_length=10, choices=FORMATS, default='pdf')
    
    # Schedule
    frequency = models.CharField(max_length=20, choices=FREQUENCIES, default='one_time')
    next_run = models.DateTimeField(null=True, blank=True)
    last_run = models.DateTimeField(null=True, blank=True)
    
    # Recipients
    recipients = models.JSONField(default=list)
    
    # File
    generated_file = models.FileField(upload_to='reports/%Y/%m/', blank=True)
    file_size = models.IntegerField(default=0)
    
    # Status
    is_active = models.BooleanField(default=True)
    
    # Owner
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['report_number']),
            models.Index(fields=['report_type']),
            models.Index(fields=['next_run']),
        ]
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        if not self.report_number:
            self.report_number = self.generate_report_number()
        super().save(*args, **kwargs)
    
    def generate_report_number(self):
        import random
        import string
        timestamp = timezone.now().strftime('%Y%m')
        random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        return f"RPT{timestamp}{random_str}"
    
    def generate(self):
        """Generate the report"""
        from .report_generators import ReportGenerator
        generator = ReportGenerator(self)
        file = generator.generate()
        
        self.generated_file = file
        self.last_run = timezone.now()
        
        if self.frequency != 'one_time':
            # Calculate next run
            if self.frequency == 'daily':
                self.next_run = timezone.now() + timezone.timedelta(days=1)
            elif self.frequency == 'weekly':
                self.next_run = timezone.now() + timezone.timedelta(weeks=1)
            elif self.frequency == 'monthly':
                self.next_run = timezone.now() + timezone.timedelta(days=30)
            elif self.frequency == 'quarterly':
                self.next_run = timezone.now() + timezone.timedelta(days=90)
        
        self.save(update_fields=['generated_file', 'last_run', 'next_run'])
        
        # Send to recipients
        self.deliver()
        
        return file
    
    def deliver(self):
        """Deliver report to recipients"""
        from django.core.mail import send_mail
        from django.core.mail import EmailMessage
        
        if not self.recipients:
            return
        
        subject = f"Report: {self.name}"
        message = f"Your requested report '{self.name}' is attached."
        
        email = EmailMessage(
            subject,
            message,
            'info@flynjet.com',
            self.recipients
        )
        
        if self.generated_file:
            email.attach_file(self.generated_file.path)
        
        email.send()


class Dashboard(TimeStampedModel):
    """User dashboards"""
    
    DASHBOARD_TYPES = (
        ('personal', 'Personal'),
        ('admin', 'Admin'),
        ('agent', 'Agent'),
        ('fleet', 'Fleet Manager'),
        ('finance', 'Finance'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='dashboards')
    
    # Dashboard Info
    name = models.CharField(max_length=200)
    dashboard_type = models.CharField(max_length=20, choices=DASHBOARD_TYPES)
    
    # Configuration
    widgets = models.JSONField(default=list)
    layout = models.JSONField(default=dict)
    filters = models.JSONField(default=dict)
    
    # Sharing
    is_shared = models.BooleanField(default=False)
    share_token = models.UUIDField(default=uuid.uuid4, unique=True)
    share_expiry = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        unique_together = ['user', 'name']
    
    def __str__(self):
        return f"{self.name} - {self.user.email}"
    
    def add_widget(self, widget_type, config):
        """Add widget to dashboard"""
        widget = {
            'id': str(uuid.uuid4()),
            'type': widget_type,
            'config': config,
            'position': len(self.widgets)
        }
        self.widgets.append(widget)
        self.save(update_fields=['widgets'])
        return widget
    
    def remove_widget(self, widget_id):
        """Remove widget from dashboard"""
        self.widgets = [w for w in self.widgets if w.get('id') != widget_id]
        self.save(update_fields=['widgets'])
    
    def get_shareable_link(self):
        """Get shareable dashboard link"""
        return f"/analytics/dashboard/shared/{self.share_token}/"
    
    def is_share_valid(self):
        """Check if share is still valid"""
        if self.share_expiry:
            return timezone.now() < self.share_expiry
        return True