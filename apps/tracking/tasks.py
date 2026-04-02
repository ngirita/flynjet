from celery import shared_task
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from .models import FlightTrack, TrackingNotification, FlightAlert
from .services import FlightTrackingService, ExternalTrackingAPI
import logging

logger = logging.getLogger(__name__)

@shared_task
def update_tracking_data():
    """Update tracking data from external sources"""
    active_tracks = FlightTrack.objects.filter(is_tracking=True)
    
    for track in active_tracks:
        update_single_track.delay(track.id)
    
    logger.info(f"Queued updates for {active_tracks.count()} tracks")
    return active_tracks.count()

@shared_task
def update_single_track(track_id):
    """Update a single track from external source"""
    try:
        track = FlightTrack.objects.get(id=track_id)
        service = FlightTrackingService(track)
        
        # Try to get data from external API
        data = ExternalTrackingAPI.get_flightradar_data(track.flight_number)
        if data:
            service.update_from_adsb(data)
        else:
            # Simulate for demo
            service.simulate_flight()
        
        logger.info(f"Updated track {track_id}")
    except FlightTrack.DoesNotExist:
        logger.error(f"Track {track_id} not found")

@shared_task
def check_flight_alerts():
    """Check and trigger flight alerts"""
    alerts = FlightAlert.objects.filter(is_active=True)
    
    for alert in alerts:
        check_single_alert.delay(alert.id)
    
    return alerts.count()

@shared_task
def check_single_alert(alert_id):
    """Check a single alert condition"""
    try:
        alert = FlightAlert.objects.select_related('track').get(id=alert_id)
        track = alert.track
        
        should_trigger = False
        value = None
        
        if alert.alert_type == 'takeoff' and track.altitude and track.altitude > 1000:
            should_trigger = True
            value = track.altitude
        elif alert.alert_type == 'landing' and track.altitude and track.altitude < 100:
            should_trigger = True
            value = track.altitude
        elif alert.alert_type == 'altitude' and alert.threshold_value:
            if track.altitude and abs(track.altitude - alert.threshold_value) < 1000:
                should_trigger = True
                value = track.altitude
        elif alert.alert_type == 'speed' and alert.threshold_value:
            if track.speed and abs(track.speed - alert.threshold_value) < 10:
                should_trigger = True
                value = track.speed
        
        if should_trigger:
            alert.trigger(value)
            
            # Create notification
            TrackingNotification.objects.create(
                track=track,
                notification_type=alert.alert_type,
                title=f'Flight Alert: {alert.get_alert_type_display()}',
                message=alert.custom_message or f'Alert triggered for {track.flight_number}',
                send_email=alert.notify_email,
                send_push=alert.notify_push,
                send_sms=alert.notify_sms
            )
            
    except FlightAlert.DoesNotExist:
        logger.error(f"Alert {alert_id} not found")

@shared_task
def send_tracking_notifications():
    """Send pending notifications"""
    notifications = TrackingNotification.objects.filter(is_sent=False)
    
    for notification in notifications:
        send_notification.delay(notification.id)
    
    return notifications.count()

@shared_task
def send_notification(notification_id):
    """Send a single notification"""
    try:
        notification = TrackingNotification.objects.select_related('track__booking__user').get(id=notification_id)
        
        if notification.send_email:
            user = notification.track.booking.user
            send_mail(
                notification.title,
                notification.message,
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=True,
            )
        
        # Mark as sent
        notification.is_sent = True
        notification.sent_at = timezone.now()
        notification.save()
        
        logger.info(f"Sent notification {notification_id}")
    except TrackingNotification.DoesNotExist:
        logger.error(f"Notification {notification_id} not found")

@shared_task
def cleanup_old_tracks(days=30):
    """Clean up old tracking data"""
    cutoff = timezone.now() - timezone.timedelta(days=days)
    old_tracks = FlightTrack.objects.filter(created_at__lt=cutoff)
    
    count = old_tracks.count()
    old_tracks.delete()
    
    logger.info(f"Cleaned up {count} old tracks")
    return count

@shared_task
def generate_tracking_report(days=7):
    """Generate tracking statistics report"""
    start_date = timezone.now() - timezone.timedelta(days=days)
    
    tracks = FlightTrack.objects.filter(created_at__gte=start_date)
    
    report = {
        'period_days': days,
        'total_tracks': tracks.count(),
        'active_tracks': tracks.filter(is_tracking=True).count(),
        'completed_tracks': tracks.filter(is_tracking=False).count(),
        'notifications_sent': TrackingNotification.objects.filter(
            created_at__gte=start_date,
            is_sent=True
        ).count(),
        'alerts_triggered': FlightAlert.objects.filter(
            last_triggered__gte=start_date
        ).count(),
    }
    
    logger.info(f"Tracking report generated: {report}")
    return report