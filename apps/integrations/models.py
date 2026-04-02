import uuid
from django.db import models
from django.utils import timezone
from apps.core.models import TimeStampedModel

class APIIntegration(TimeStampedModel):
    """Third-party API integrations"""
    
    INTEGRATION_TYPES = (
        ('weather', 'Weather Service'),
        ('flight_data', 'Flight Data'),
        ('fuel_prices', 'Fuel Prices'),
        ('currency', 'Currency Exchange'),
        ('payment', 'Payment Gateway'),
        ('email', 'Email Service'),
        ('sms', 'SMS Service'),
        ('maps', 'Maps Service'),
        ('insurance', 'Insurance API'),
        ('customs', 'Customs API'),
    )
    
    AUTH_TYPES = (
        ('api_key', 'API Key'),
        ('oauth2', 'OAuth 2.0'),
        ('basic', 'Basic Auth'),
        ('jwt', 'JWT'),
        ('none', 'No Auth'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    integration_type = models.CharField(max_length=20, choices=INTEGRATION_TYPES)
    
    # Connection Details
    base_url = models.URLField()
    auth_type = models.CharField(max_length=20, choices=AUTH_TYPES)
    
    # Authentication Credentials (encrypted)
    api_key = models.CharField(max_length=500, blank=True)
    api_secret = models.CharField(max_length=500, blank=True)
    client_id = models.CharField(max_length=500, blank=True)
    client_secret = models.CharField(max_length=500, blank=True)
    
    # OAuth2 Specific
    access_token = models.TextField(blank=True)
    refresh_token = models.TextField(blank=True)
    token_expires_at = models.DateTimeField(null=True, blank=True)
    
    # Configuration
    config = models.JSONField(default=dict)
    headers = models.JSONField(default=dict)
    
    # Rate Limiting
    rate_limit = models.IntegerField(default=0, help_text="Requests per minute, 0 for unlimited")
    
    # Status
    is_active = models.BooleanField(default=True)
    last_checked = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['integration_type']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return self.name
    
    def is_token_valid(self):
        """Check if OAuth token is still valid"""
        if self.token_expires_at:
            return timezone.now() < self.token_expires_at
        return False
    
    def record_error(self, error):
        """Record integration error"""
        self.last_error = error[:1000]  # Truncate if too long
        self.last_checked = timezone.now()
        self.save(update_fields=['last_error', 'last_checked'])


class WebhookEndpoint(TimeStampedModel):
    """Webhook endpoints for receiving data"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    
    # Endpoint
    path = models.CharField(max_length=200, unique=True)
    secret = models.CharField(max_length=100)
    
    # Events to listen for
    events = models.JSONField(default=list)
    
    # Processing
    handler_function = models.CharField(max_length=200)
    
    # Security
    allowed_ips = models.JSONField(default=list)
    require_signature = models.BooleanField(default=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['path']),
        ]
    
    def __str__(self):
        return self.name
    
    def verify_signature(self, payload, signature):
        """Verify webhook signature"""
        import hmac
        import hashlib
        
        expected = hmac.new(
            self.secret.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(expected, signature)


class WebhookDelivery(TimeStampedModel):
    """Webhook delivery attempts"""
    
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('delivered', 'Delivered'),
        ('failed', 'Failed'),
        ('retrying', 'Retrying'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    webhook = models.ForeignKey(WebhookEndpoint, on_delete=models.CASCADE, related_name='deliveries')
    
    # Event
    event_type = models.CharField(max_length=100)
    payload = models.JSONField()
    
    # Delivery
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    attempts = models.IntegerField(default=0)
    last_attempt = models.DateTimeField(null=True, blank=True)
    
    # Response
    response_status = models.IntegerField(null=True, blank=True)
    response_body = models.TextField(blank=True)
    
    # Error
    error_message = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['event_type']),
        ]
    
    def __str__(self):
        return f"Webhook {self.webhook.name} - {self.event_type}"
    
    def mark_delivered(self, response_status, response_body):
        """Mark as delivered"""
        self.status = 'delivered'
        self.response_status = response_status
        self.response_body = response_body[:5000]  # Truncate
        self.save(update_fields=['status', 'response_status', 'response_body'])
    
    def mark_failed(self, error):
        """Mark as failed"""
        self.status = 'failed'
        self.error_message = str(error)[:500]  # Truncate
        self.save(update_fields=['status', 'error_message'])


class WeatherCache(models.Model):
    """Cached weather data"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    location_key = models.CharField(max_length=100, db_index=True)
    
    # Location
    latitude = models.FloatField()
    longitude = models.FloatField()
    
    # Weather Data
    temperature = models.FloatField()
    feels_like = models.FloatField()
    humidity = models.IntegerField()
    pressure = models.FloatField()
    wind_speed = models.FloatField()
    wind_direction = models.IntegerField()
    conditions = models.CharField(max_length=200)
    icon = models.CharField(max_length=50)
    
    # Forecast
    forecast = models.JSONField(default=list)
    
    # Cache Control
    fetched_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField()
    
    class Meta:
        indexes = [
            models.Index(fields=['location_key']),
            models.Index(fields=['expires_at']),
        ]
    
    def __str__(self):
        return f"Weather for {self.location_key}"
    
    def is_expired(self):
        """Check if cache is expired"""
        return timezone.now() >= self.expires_at


class FuelPriceCache(models.Model):
    """Cached fuel prices"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    location_code = models.CharField(max_length=10, db_index=True)
    
    # Fuel Prices
    jet_a_price = models.DecimalField(max_digits=10, decimal_places=2)
    avgas_price = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')
    
    # Cache Control
    fetched_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField()
    
    class Meta:
        indexes = [
            models.Index(fields=['location_code']),
            models.Index(fields=['expires_at']),
        ]
    
    def __str__(self):
        return f"Fuel prices for {self.location_code}"
    
    def is_expired(self):
        """Check if cache is expired"""
        return timezone.now() >= self.expires_at


class ExchangeRateCache(models.Model):
    """Cached currency exchange rates"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    from_currency = models.CharField(max_length=3)
    to_currency = models.CharField(max_length=3)
    
    # Rate
    rate = models.DecimalField(max_digits=20, decimal_places=6)
    
    # Cache Control
    fetched_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField()
    
    class Meta:
        unique_together = ['from_currency', 'to_currency']
        indexes = [
            models.Index(fields=['expires_at']),
        ]
    
    def __str__(self):
        return f"1 {self.from_currency} = {self.rate} {self.to_currency}"
    
    def is_expired(self):
        """Check if cache is expired"""
        return timezone.now() >= self.expires_at