from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from .models import FlightTrack, TrackingNotification
from apps.bookings.models import Booking
from apps.bookings.signals import booking_confirmed, booking_cancelled
import logging

logger = logging.getLogger(__name__)

@receiver(post_save, sender=Booking)
def create_track_on_booking_confirmation(sender, instance, created, **kwargs):
    """Create flight track when booking is confirmed"""
    if instance.status == 'confirmed' and not hasattr(instance, 'tracking'):
        from .services import FlightTrackingService
        FlightTrackingService.create_track_from_booking(instance)
        logger.info(f"Created flight track for booking {instance.booking_reference}")

@receiver(booking_cancelled)
def handle_booking_cancelled(sender, booking, **kwargs):
    """Handle booking cancellation"""
    try:
        track = FlightTrack.objects.get(booking=booking)
        track.is_tracking = False
        track.save()
        
        # Create cancellation notification
        TrackingNotification.objects.create(
            track=track,
            notification_type='system',
            title='Flight Cancelled',
            message=f'Flight {track.flight_number} has been cancelled'
        )
        logger.info(f"Tracking stopped for cancelled booking {booking.booking_reference}")
    except FlightTrack.DoesNotExist:
        pass

@receiver(post_save, sender=FlightTrack)
def track_position_changed(sender, instance, created, **kwargs):
    """Handle position changes"""
    if not created and instance.tracker.has_changed('latitude'):
        # Position changed
        old_lat = instance.tracker.previous('latitude')
        old_lon = instance.tracker.previous('longitude')
        
        if old_lat and old_lon:
            # Calculate distance moved
            from .utils import calculate_distance
            distance = calculate_distance(old_lat, old_lon, instance.latitude, instance.longitude)
            
            # Create notification for significant movement (> 10 nm)
            if distance > 10:
                TrackingNotification.objects.create(
                    track=instance,
                    notification_type='position',
                    title='Position Update',
                    message=f'Flight {instance.flight_number} has moved {distance:.1f} nm'
                )

@receiver(post_save, sender=FlightTrack)
def check_arrival(sender, instance, **kwargs):
    """Check if flight has arrived"""
    if instance.estimated_arrival and instance.estimated_arrival <= timezone.now():
        if instance.progress_percentage < 100:
            # Flight should have arrived but hasn't
            TrackingNotification.objects.create(
                track=instance,
                notification_type='delay',
                title='Flight Delayed',
                message=f'Flight {instance.flight_number} is delayed'
            )
        elif instance.progress_percentage >= 100 and not instance.notifications.filter(notification_type='arrival').exists():
            # Flight has arrived
            TrackingNotification.objects.create(
                track=instance,
                notification_type='arrival',
                title='Flight Arrived',
                message=f'Flight {instance.flight_number} has arrived at {instance.arrival_airport}'
            )

@receiver(post_save, sender=FlightTrack)
def update_eta(sender, instance, **kwargs):
    """Update ETA based on current speed and position"""
    if instance.speed and instance.distance_remaining:
        hours_remaining = instance.distance_remaining / instance.speed
        new_eta = timezone.now() + timezone.timedelta(hours=hours_remaining)
        
        if instance.estimated_arrival:
            # Check if ETA changed significantly
            diff = abs((new_eta - instance.estimated_arrival).total_seconds() / 60)
            if diff > 15:  # More than 15 minutes difference
                TrackingNotification.objects.create(
                    track=instance,
                    notification_type='delay',
                    title='ETA Updated',
                    message=f'New estimated arrival: {new_eta.strftime("%H:%M")}'
                )