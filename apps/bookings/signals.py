from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver, Signal
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone
from django.conf import settings
from .models import Booking, BookingHistory, Invoice
from apps.payments.models import Payment
from apps.core.models import Notification, ActivityLog
from apps.airports.models import Airport
import logging

logger = logging.getLogger(__name__)

# ============ SIGNAL DEFINITIONS ============
booking_confirmed = Signal()
booking_cancelled = Signal()
# ============================================

@receiver(post_save, sender=Booking)
def create_booking_history(sender, instance, created, **kwargs):
    """Create booking history entry when booking is created or updated."""
    if created:
        # New booking created
        BookingHistory.objects.create(
            booking=instance,
            old_status='',
            new_status=instance.status,
            changed_by=instance.user if hasattr(instance, 'user') else None,
            reason='Booking created'
        )
        
        # Send booking confirmation email
        send_booking_confirmation_email(instance)
        
        # Create notification for user
        Notification.objects.create(
            recipient=instance.user,
            notification_type='booking',
            title='Booking Created',
            message=f'Your booking {instance.booking_reference} has been created successfully.',
            related_object=instance
        )
        
        logger.info(f"Booking {instance.booking_reference} created by {instance.user.email}")
    
    else:
        # Check if status changed
        try:
            old_instance = Booking.objects.get(pk=instance.pk)
            if old_instance.status != instance.status:
                # Status changed
                BookingHistory.objects.create(
                    booking=instance,
                    old_status=old_instance.status,
                    new_status=instance.status,
                    changed_by=instance.user if hasattr(instance, 'user') else None,
                    reason=f'Status changed from {old_instance.status} to {instance.status}'
                )
                
                # Send status update email
                send_booking_status_update_email(instance, old_instance.status)
                
                # Create notification
                Notification.objects.create(
                    recipient=instance.user,
                    notification_type='booking',
                    title='Booking Status Updated',
                    message=f'Your booking {instance.booking_reference} status changed to {instance.get_status_display()}.',
                    related_object=instance
                )
                
                # Send custom signals for tracking
                if instance.status == 'confirmed':
                    booking_confirmed.send(sender=Booking, booking=instance, user=instance.user)
                    logger.info(f"Booking confirmed signal sent for {instance.booking_reference}")
                elif instance.status == 'cancelled':
                    booking_cancelled.send(sender=Booking, booking=instance, user=instance.user)
                    logger.info(f"Booking cancelled signal sent for {instance.booking_reference}")
                
                logger.info(f"Booking {instance.booking_reference} status changed to {instance.status}")
        
        except Booking.DoesNotExist:
            pass


@receiver(pre_save, sender=Booking)
def set_booking_dates(sender, instance, **kwargs):
    """Set calculated fields before saving."""
    if not instance.pk:  # New booking
        # Set payment due date (24 hours from creation)
        if not instance.payment_due_date:
            instance.payment_due_date = timezone.now() + timezone.timedelta(hours=24)
        
        # Set cancellation deadline (48 hours before departure)
        if instance.departure_datetime and not instance.cancellation_deadline:
            instance.cancellation_deadline = instance.departure_datetime - timezone.timedelta(hours=48)
    
    # Calculate totals if not set
    if not instance.total_amount_usd or instance.total_amount_usd == 0:
        instance.calculate_totals()


@receiver(post_save, sender=Booking)
def create_invoice_for_booking(sender, instance, created, **kwargs):
    """Create invoice when booking is confirmed."""
    if instance.status == 'confirmed' and not instance.invoices.exists():
        from apps.bookings.models import Invoice
        
        # Get airport names for invoice description
        departure_name = instance.departure_airport
        arrival_name = instance.arrival_airport
        
        try:
            dep_airport = Airport.objects.get(iata_code=instance.departure_airport)
            departure_name = f"{dep_airport.name} ({dep_airport.iata_code})"
        except Airport.DoesNotExist:
            departure_name = instance.departure_airport
        
        try:
            arr_airport = Airport.objects.get(iata_code=instance.arrival_airport)
            arrival_name = f"{arr_airport.name} ({arr_airport.iata_code})"
        except Airport.DoesNotExist:
            arrival_name = instance.arrival_airport
        
        invoice = Invoice.objects.create(
            booking=instance,
            user=instance.user,
            invoice_date=timezone.now().date(),
            due_date=timezone.now().date() + timezone.timedelta(days=7),
            subtotal_usd=instance.total_amount_usd - instance.tax_amount_usd,
            tax_rate=10,
            tax_amount_usd=instance.tax_amount_usd,
            total_usd=instance.total_amount_usd,
            total_currency=instance.total_amount_usd,
            currency='USD',
            billing_address_line1=instance.user.address_line1 or 'Not provided',
            billing_city=instance.user.city or 'Not provided',
            billing_state=instance.user.state or 'Not provided',
            billing_postal_code=instance.user.postal_code or '00000',
            billing_country=instance.user.country or 'US',
        )
                
        # Create invoice items with airport names
        invoice.items.create(
            description=f"Flight from {departure_name} to {arrival_name}",
            quantity=1,
            unit_price_usd=instance.base_price_usd,
            line_total_usd=instance.base_price_usd
        )
        
        if instance.fuel_surcharge_usd > 0:
            invoice.items.create(
                description="Fuel Surcharge",
                quantity=1,
                unit_price_usd=instance.fuel_surcharge_usd,
                line_total_usd=instance.fuel_surcharge_usd
            )
        
        logger.info(f"Invoice created for booking {instance.booking_reference}")


@receiver(post_save, sender=Booking)
def update_aircraft_availability(sender, instance, **kwargs):
    """Update aircraft availability when booking is confirmed or cancelled."""
    from apps.fleet.models import AircraftAvailability
    
    try:
        if instance.status == 'confirmed':
            # First, clean up any existing records for this booking to avoid duplicates
            AircraftAvailability.objects.filter(booking=instance).delete()
            
            # Create availability block - use get_or_create with error handling
            avail, created = AircraftAvailability.objects.get_or_create(
                aircraft=instance.aircraft,
                start_datetime=instance.departure_datetime,
                end_datetime=instance.arrival_datetime,
                defaults={
                    'is_available': False,
                    'booking': instance,
                    'reason': f"Booked: {instance.booking_reference}"
                }
            )
            
            if not created:
                # If it exists but not linked to this booking, update it
                if avail.booking != instance:
                    avail.booking = instance
                    avail.is_available = False
                    avail.reason = f"Booked: {instance.booking_reference}"
                    avail.save()
                    logger.info(f"Updated existing availability record for booking {instance.booking_reference}")
            else:
                logger.info(f"Aircraft {instance.aircraft.registration_number} blocked for booking {instance.booking_reference}")
        
        elif instance.status in ['cancelled', 'completed']:
            # Remove availability block for this booking
            deleted_count = AircraftAvailability.objects.filter(booking=instance).delete()[0]
            if deleted_count > 0:
                logger.info(f"Aircraft availability restored for booking {instance.booking_reference} (removed {deleted_count} records)")
            else:
                # Try to find by date range if no booking reference
                records = AircraftAvailability.objects.filter(
                    aircraft=instance.aircraft,
                    start_datetime=instance.departure_datetime,
                    end_datetime=instance.arrival_datetime,
                    is_available=False
                )
                deleted_count = records.delete()[0]
                if deleted_count > 0:
                    logger.info(f"Aircraft availability restored for booking {instance.booking_reference} by date range (removed {deleted_count} records)")
    
    except Exception as e:
        logger.error(f"Error updating aircraft availability for booking {instance.booking_reference}: {str(e)}")
        # Don't raise the exception to prevent breaking the booking save


@receiver(post_delete, sender=Booking)
def log_booking_deletion(sender, instance, **kwargs):
    """Log when booking is deleted."""
    ActivityLog.objects.create(
        user=instance.user,
        activity_type='booking_deleted',
        description=f'Booking {instance.booking_reference} was deleted',
        related_object=instance
    )
    logger.info(f"Booking {instance.booking_reference} deleted")


# Helper functions for sending emails
def send_booking_confirmation_email(booking):
    """Send booking confirmation email with airport names."""
    subject = f"Booking Confirmation - {booking.booking_reference}"
    
    # Get airport details
    departure_airport = None
    arrival_airport = None
    
    if booking.departure_airport:
        try:
            departure_airport = Airport.objects.get(iata_code=booking.departure_airport)
        except Airport.DoesNotExist:
            pass
    
    if booking.arrival_airport:
        try:
            arrival_airport = Airport.objects.get(iata_code=booking.arrival_airport)
        except Airport.DoesNotExist:
            pass
    
    context = {
        'booking': booking,
        'user': booking.user,
        'aircraft': booking.aircraft,
        'departure_airport': departure_airport,
        'arrival_airport': arrival_airport,
        'departure_iata': booking.departure_airport,
        'arrival_iata': booking.arrival_airport,
    }
    
    html_message = render_to_string('emails/booking_confirmation.html', context)
    plain_message = render_to_string('emails/booking_confirmation.txt', context)
    
    try:
        send_mail(
            subject,
            plain_message,
            settings.DEFAULT_FROM_EMAIL,
            [booking.user.email],
            html_message=html_message,
            fail_silently=False,
        )
        logger.info(f"Confirmation email sent for booking {booking.booking_reference}")
    except Exception as e:
        logger.error(f"Failed to send confirmation email for booking {booking.booking_reference}: {e}")


def send_booking_status_update_email(booking, old_status):
    """Send booking status update email with airport names."""
    subject = f"Booking Status Update - {booking.booking_reference}"
    
    # Get airport details
    departure_airport = None
    arrival_airport = None
    
    if booking.departure_airport:
        try:
            departure_airport = Airport.objects.get(iata_code=booking.departure_airport)
        except Airport.DoesNotExist:
            pass
    
    if booking.arrival_airport:
        try:
            arrival_airport = Airport.objects.get(iata_code=booking.arrival_airport)
        except Airport.DoesNotExist:
            pass
    
    context = {
        'booking': booking,
        'user': booking.user,
        'old_status': old_status,
        'new_status': booking.status,
        'departure_airport': departure_airport,
        'arrival_airport': arrival_airport,
        'departure_iata': booking.departure_airport,
        'arrival_iata': booking.arrival_airport,
    }
    
    html_message = render_to_string('emails/booking_status_update.html', context)
    plain_message = render_to_string('emails/booking_status_update.txt', context)
    
    try:
        send_mail(
            subject,
            plain_message,
            settings.DEFAULT_FROM_EMAIL,
            [booking.user.email],
            html_message=html_message,
            fail_silently=False,
        )
        logger.info(f"Status update email sent for booking {booking.booking_reference}")
    except Exception as e:
        logger.error(f"Failed to send status update email for booking {booking.booking_reference}: {e}")


@receiver(post_save, sender=Booking)
def check_duplicate_bookings(sender, instance, created, **kwargs):
    """Check for duplicate bookings."""
    if created:
        # Check if user already has a booking for same time period
        duplicate = Booking.objects.filter(
            user=instance.user,
            departure_datetime__date=instance.departure_datetime.date(),
            status__in=['draft', 'pending', 'confirmed']
        ).exclude(pk=instance.pk).exists()
        
        if duplicate:
            Notification.objects.create(
                recipient=instance.user,
                notification_type='system',
                priority='medium',
                title='Potential Duplicate Booking',
                message=f'You have another booking on {instance.departure_datetime.date()}. Please verify.',
                related_object=instance
            )
            logger.warning(f"Potential duplicate booking detected for user {instance.user.email}")


@receiver(pre_save, sender=Booking)
def validate_booking_dates(sender, instance, **kwargs):
    """Validate booking dates before saving."""
    if instance.departure_datetime and instance.arrival_datetime:
        # Check if arrival is after departure
        if instance.arrival_datetime <= instance.departure_datetime:
            raise ValueError("Arrival time must be after departure time")
        
        # Check minimum duration (1 hour)
        min_duration = timezone.timedelta(hours=15)
        if instance.arrival_datetime - instance.departure_datetime < min_duration:
            raise ValueError("Minimum flight duration is 15 hour")
        
        # Check if departure is in the past (for new bookings)
        if not instance.pk and instance.departure_datetime < timezone.now():
            raise ValueError("Departure time cannot be in the past")