from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
from .models import Aircraft, AircraftMaintenance, AircraftDocument, AircraftStatusHistory
import logging

logger = logging.getLogger(__name__)

@receiver(pre_save, sender=Aircraft)
def track_aircraft_status_changes(sender, instance, **kwargs):
    """Track when aircraft status changes"""
    if instance.pk:
        try:
            old_instance = Aircraft.objects.get(pk=instance.pk)
            if old_instance.status != instance.status:
                # Create status history entry
                AircraftStatusHistory.objects.create(
                    aircraft=instance,
                    old_status=old_instance.status,
                    new_status=instance.status,
                    reason=f"Status changed from {old_instance.status} to {instance.status}"
                )
                logger.info(f"Aircraft {instance.registration_number} status changed from {old_instance.status} to {instance.status}")
        except Aircraft.DoesNotExist:
            pass

@receiver(post_save, sender=AircraftMaintenance)
def update_aircraft_status_on_maintenance(sender, instance, created, **kwargs):
    """Update aircraft status when maintenance is scheduled"""
    if created and instance.status == 'scheduled':
        instance.aircraft.status = 'maintenance'
        instance.aircraft.save()
        logger.info(f"Aircraft {instance.aircraft.registration_number} set to maintenance for scheduled work")

@receiver(post_save, sender=AircraftMaintenance)
def check_maintenance_completion(sender, instance, **kwargs):
    """Check if maintenance is completed and update aircraft status"""
    if instance.status == 'completed' and instance.actual_end:
        # Check if there are any other active maintenance
        other_maintenance = AircraftMaintenance.objects.filter(
            aircraft=instance.aircraft,
            status__in=['scheduled', 'in_progress']
        ).exclude(id=instance.id).exists()
        
        if not other_maintenance:
            instance.aircraft.status = 'available'
            instance.aircraft.save()
            logger.info(f"Aircraft {instance.aircraft.registration_number} returned to available after maintenance")

@receiver(post_save, sender=AircraftDocument)
def check_document_expiry(sender, instance, created, **kwargs):
    """Check document expiry dates"""
    if instance.expiry_date:
        days_until_expiry = (instance.expiry_date - timezone.now().date()).days
        
        if days_until_expiry <= 30 and days_until_expiry > 0:
            # Document expiring soon
            from apps.core.models import Notification
            Notification.objects.create(
                recipient_type='admins',
                notification_type='system',
                priority='high',
                title='Document Expiring Soon',
                message=f"Document {instance.title} for aircraft {instance.aircraft.registration_number} expires in {days_until_expiry} days",
                related_object=instance
            )
            logger.warning(f"Document {instance.id} expires in {days_until_expiry} days")
        
        elif days_until_expiry <= 0:
            # Document expired
            instance.is_approved = False
            instance.save()
            
            from apps.core.models import Notification
            Notification.objects.create(
                recipient_type='admins',
                notification_type='system',
                priority='urgent',
                title='Document Expired',
                message=f"Document {instance.title} for aircraft {instance.aircraft.registration_number} has expired",
                related_object=instance
            )
            logger.error(f"Document {instance.id} has expired")

@receiver(post_save, sender=Aircraft)
def update_fleet_stats(sender, instance, **kwargs):
    """Update fleet statistics when aircraft is modified"""
    from .models import FleetStats
    today = timezone.now().date()
    
    # Get or create today's stats
    stats, created = FleetStats.objects.get_or_create(date=today)
    
    # Update counts
    stats.total_aircraft = Aircraft.objects.count()
    stats.available_aircraft = Aircraft.objects.filter(status='available').count()
    stats.in_maintenance = Aircraft.objects.filter(status='maintenance').count()
    stats.booked_aircraft = Aircraft.objects.filter(status='booked').count()
    
    # Calculate utilization (simplified)
    total_flight_hours = sum(a.total_flight_hours for a in Aircraft.objects.all())
    stats.total_flight_hours = total_flight_hours
    
    if stats.total_aircraft > 0:
        stats.average_utilization_rate = (stats.available_aircraft / stats.total_aircraft) * 100
    
    stats.save()
    logger.info(f"Fleet stats updated for {today}")

@receiver(post_delete, sender=Aircraft)
def log_aircraft_deletion(sender, instance, **kwargs):
    """Log when aircraft is deleted"""
    from apps.core.models import ActivityLog
    ActivityLog.objects.create(
        activity_type='admin_action',
        description=f"Aircraft {instance.registration_number} ({instance.model}) was deleted",
        data={'aircraft_id': str(instance.id), 'registration': instance.registration_number}
    )
    logger.warning(f"Aircraft {instance.registration_number} deleted")

@receiver(post_save, sender=Aircraft)
def send_low_hours_alert(sender, instance, **kwargs):
    """Send alert when aircraft approaches maintenance"""
    if instance.total_flight_hours and instance.next_maintenance_due:
        hours_until_maintenance = instance.next_maintenance_due - instance.total_flight_hours
        
        if hours_until_maintenance <= 50 and hours_until_maintenance > 0:
            from apps.core.models import Notification
            Notification.objects.create(
                recipient_type='maintenance',
                notification_type='system',
                priority='high',
                title='Maintenance Due Soon',
                message=f"Aircraft {instance.registration_number} requires maintenance in {hours_until_maintenance:.0f} flight hours",
                related_object=instance
            )
            logger.info(f"Maintenance alert for {instance.registration_number}: {hours_until_maintenance:.0f} hours remaining")