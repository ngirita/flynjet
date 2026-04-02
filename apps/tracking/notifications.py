from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from .models import TrackingNotification
import logging

logger = logging.getLogger(__name__)

class NotificationService:
    """Handle tracking notifications"""
    
    @classmethod
    def send_notification(cls, notification):
        """Send notification through all channels"""
        if notification.send_email:
            cls.send_email(notification)
        
        if notification.send_push:
            cls.send_push(notification)
        
        if notification.send_sms:
            cls.send_sms(notification)
    
    @classmethod
    def send_email(cls, notification):
        """Send email notification"""
        user = notification.track.booking.user
        
        context = {
            'notification': notification,
            'track': notification.track,
            'user': user
        }
        
        html_message = render_to_string('emails/tracking_notification.html', context)
        plain_message = render_to_string('emails/tracking_notification.txt', context)
        
        try:
            send_mail(
                notification.title,
                plain_message,
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                html_message=html_message,
                fail_silently=False,
            )
            logger.info(f"Email sent for notification {notification.id}")
        except Exception as e:
            logger.error(f"Failed to send email for notification {notification.id}: {e}")
    
    @classmethod
    def send_push(cls, notification):
        """Send push notification"""
        # Implement push notification service (Firebase, OneSignal, etc.)
        logger.info(f"Push notification would be sent for {notification.id}")
    
    @classmethod
    def send_sms(cls, notification):
        """Send SMS notification"""
        # Implement SMS service (Twilio, etc.)
        logger.info(f"SMS would be sent for {notification.id}")
    
    @classmethod
    def create_notification(cls, track, notif_type, title, message, **kwargs):
        """Create and send notification"""
        notification = TrackingNotification.objects.create(
            track=track,
            notification_type=notif_type,
            title=title,
            message=message,
            **kwargs
        )
        
        cls.send_notification(notification)
        return notification
    
    @classmethod
    def notify_position_change(cls, track, old_position, new_position):
        """Notify significant position change"""
        from .utils import calculate_distance
        
        distance = calculate_distance(
            old_position['lat'], old_position['lng'],
            new_position['lat'], new_position['lng']
        )
        
        if distance > 50:  # Significant position change (>50 nm)
            cls.create_notification(
                track,
                'position',
                'Position Update',
                f"Flight {track.flight_number} has traveled {distance:.0f} nm"
            )
    
    @classmethod
    def notify_altitude_change(cls, track, old_alt, new_alt):
        """Notify significant altitude change"""
        if old_alt and new_alt:
            change = abs(new_alt - old_alt)
            if change > 5000:  # Significant altitude change (>5000 ft)
                direction = "climbing to" if new_alt > old_alt else "descending to"
                cls.create_notification(
                    track,
                    'altitude',
                    'Altitude Change',
                    f"Flight {track.flight_number} is {direction} {new_alt:.0f} ft"
                )
    
    @classmethod
    def notify_speed_change(cls, track, old_speed, new_speed):
        """Notify significant speed change"""
        if old_speed and new_speed:
            change = abs(new_speed - old_speed)
            if change > 50:  # Significant speed change (>50 knots)
                cls.create_notification(
                    track,
                    'speed',
                    'Speed Change',
                    f"Flight {track.flight_number} speed changed to {new_speed:.0f} knots"
                )
    
    @classmethod
    def notify_arrival(cls, track):
        """Notify flight arrival"""
        cls.create_notification(
            track,
            'arrival',
            'Flight Arrived',
            f"Flight {track.flight_number} has arrived at {track.arrival_airport}"
        )
    
    @classmethod
    def notify_departure(cls, track):
        """Notify flight departure"""
        cls.create_notification(
            track,
            'departure',
            'Flight Departed',
            f"Flight {track.flight_number} has departed from {track.departure_airport}"
        )
    
    @classmethod
    def notify_delay(cls, track, delay_minutes):
        """Notify flight delay"""
        cls.create_notification(
            track,
            'delay',
            'Flight Delayed',
            f"Flight {track.flight_number} is delayed by {delay_minutes} minutes"
        )