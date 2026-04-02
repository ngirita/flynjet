from django.core.exceptions import ValidationError
from django.utils import timezone
import re

def validate_iata_code(value):
    """Validate IATA airport code."""
    if not re.match(r'^[A-Z]{3}$', value):
        raise ValidationError('IATA code must be 3 uppercase letters.')

def validate_airport_exists(value):
    """Validate that the airport exists in our database."""
    from apps.airports.models import Airport
    
    if value:
        try:
            Airport.objects.get(iata_code=value)
        except Airport.DoesNotExist:
            raise ValidationError(f'Airport with code "{value}" does not exist in our database. Please check the IATA code.')

def validate_future_datetime(value):
    """Validate datetime is in the future."""
    if value <= timezone.now():
        raise ValidationError('Datetime must be in the future.')

def validate_booking_dates(departure, arrival):
    """Validate booking dates."""
    if departure >= arrival:
        raise ValidationError('Arrival time must be after departure time.')
    
    min_duration = timezone.timedelta(hours=15)
    if arrival - departure < min_duration:
        raise ValidationError('Minimum flight duration is 15 hour.')
    
    # Maximum flight duration (e.g., 24 hours for private jets)
    max_duration = timezone.timedelta(hours=24)
    if arrival - departure > max_duration:
        raise ValidationError('Maximum flight duration is 24 hours.')

def validate_passenger_count(value):
    """Validate passenger count."""
    if value < 1:
        raise ValidationError('At least 1 passenger required.')
    if value > 100:
        raise ValidationError('Maximum 100 passengers allowed.')

def validate_phone_number(value):
    """Validate phone number format."""
    # More comprehensive phone number validation
    # Accepts formats: +1234567890, 1234567890, (123) 456-7890, etc.
    phone_regex = re.compile(r'^[\+]?[(]?[0-9]{1,3}[)]?[-\s\.]?[(]?[0-9]{1,4}[)]?[-\s\.]?[0-9]{1,4}[-\s\.]?[0-9]{1,9}$')
    if not phone_regex.match(value):
        raise ValidationError('Invalid phone number format. Please use international format (e.g., +1234567890)')

def validate_passport_number(value):
    """Validate passport number format."""
    # More comprehensive passport validation
    # Most passports are alphanumeric, 6-12 characters
    passport_regex = re.compile(r'^[A-Z0-9]{6,12}$')
    if not passport_regex.match(value):
        raise ValidationError('Invalid passport number format. Must be 6-12 alphanumeric characters.')

def validate_airport_pair(departure_iata, arrival_iata):
    """Validate that departure and arrival airports are different."""
    if departure_iata and arrival_iata and departure_iata == arrival_iata:
        raise ValidationError('Departure and arrival airports must be different.')

def validate_booking_time_window(departure_datetime, arrival_datetime):
    """
    Validate that the booking is within acceptable time windows.
    e.g., cannot book less than 2 hours before departure
    """
    now = timezone.now()
    min_advance = timezone.timedelta(hours=2)
    
    if departure_datetime and departure_datetime < now + min_advance:
        raise ValidationError(f'Bookings must be made at least {min_advance.seconds//3600} hours in advance.')

# Optional: Class-based validators for use with Django REST Framework
class IATAValidator:
    """Validator class for IATA codes that can be used with DRF."""
    
    def __call__(self, value):
        validate_iata_code(value)
        return value
    
    def __repr__(self):
        return "IATAValidator()"

class AirportExistsValidator:
    """Validator to ensure airport exists in database."""
    
    def __call__(self, value):
        validate_airport_exists(value)
        return value
    
    def __repr__(self):
        return "AirportExistsValidator()"

class FutureDateTimeValidator:
    """Validator to ensure datetime is in the future."""
    
    def __call__(self, value):
        validate_future_datetime(value)
        return value
    
    def __repr__(self):
        return "FutureDateTimeValidator()"

# Combined validators for common use cases
def validate_booking_airports(departure, arrival):
    """Combined validation for booking airports."""
    if departure:
        validate_iata_code(departure)
        validate_airport_exists(departure)
    
    if arrival:
        validate_iata_code(arrival)
        validate_airport_exists(arrival)
    
    validate_airport_pair(departure, arrival)

def validate_complete_booking(departure_iata, arrival_iata, departure_datetime, arrival_datetime, passenger_count):
    """
    Combined validation for complete booking.
    This is useful for form validation or API endpoint validation.
    """
    # Validate airports
    validate_booking_airports(departure_iata, arrival_iata)
    
    # Validate dates
    if departure_datetime and arrival_datetime:
        validate_future_datetime(departure_datetime)
        validate_booking_dates(departure_datetime, arrival_datetime)
        validate_booking_time_window(departure_datetime, arrival_datetime)
    
    # Validate passenger count
    if passenger_count:
        validate_passenger_count(passenger_count)