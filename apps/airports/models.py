import uuid
from django.db import models
from django.core.validators import RegexValidator

class Airport(models.Model):
    """
    Airport model with both IATA codes and user-friendly names.
    IATA codes are stored as the primary identifier for internal use,
    but we provide full names for display.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Primary identifier (used internally)
    iata_code = models.CharField(
        max_length=3, 
        unique=True, 
        db_index=True,
        validators=[RegexValidator(r'^[A-Z]{3}$', 'IATA code must be 3 uppercase letters.')],
        help_text="3-letter IATA airport code (e.g., JFK, LHR)"
    )
    icao_code = models.CharField(max_length=4, blank=True, db_index=True)
    
    # User-friendly information
    name = models.CharField(max_length=200, help_text="Full airport name")
    city = models.CharField(max_length=100, db_index=True)
    country = models.CharField(max_length=100, db_index=True)
    country_code = models.CharField(max_length=2, blank=True, help_text="ISO country code")
    
    # Geographical data (useful for distance calculations)
    latitude = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    timezone = models.CharField(max_length=50, blank=True)
    
    # Additional details
    elevation_ft = models.IntegerField(null=True, blank=True)
    website = models.URLField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    
    # Status
    is_active = models.BooleanField(default=True, db_index=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['city', 'name']
        indexes = [
            models.Index(fields=['iata_code']),
            models.Index(fields=['city', 'country']),
            models.Index(fields=['name']),
        ]
        verbose_name = "Airport"
        verbose_name_plural = "Airports"
    
    def __str__(self):
        return f"{self.city} ({self.iata_code})"
    
    @property
    def display_name(self):
        """Return user-friendly display name"""
        return f"{self.name} ({self.iata_code}), {self.city}"
    
    @property
    def short_display(self):
        """Return short display name for dropdowns"""
        return f"{self.city} ({self.iata_code})"
    
    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('airports:detail', args=[self.iata_code])