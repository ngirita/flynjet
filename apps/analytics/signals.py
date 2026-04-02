# apps/analytics/signals.py - FIXED VERSION

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from .models import AnalyticsEvent, DailyMetric
from apps.bookings.models import Booking
from apps.payments.models import Payment
from apps.accounts.models import User
import logging
import uuid

logger = logging.getLogger(__name__)

@receiver(post_save, sender=Booking)
def track_booking_created(sender, instance, created, **kwargs):
    """Track booking creation events"""
    if created:
        # Generate unique event ID with UUID to prevent duplicates
        event_id = f"booking_{instance.id}_{uuid.uuid4().hex[:8]}"
        
        if not AnalyticsEvent.objects.filter(event_id=event_id).exists():
            AnalyticsEvent.objects.create(
                event_id=event_id,
                event_type='booking_created',
                timestamp=timezone.now(),
                user=instance.user,
                data={
                    'booking_id': str(instance.id),
                    'reference': instance.booking_reference,
                    'amount': float(instance.total_amount_usd),
                    'route': f"{instance.departure_airport} → {instance.arrival_airport}"
                }
            )
            logger.info(f"Tracked booking creation for {instance.booking_reference}")

@receiver(post_save, sender=Booking)
def track_booking_completion(sender, instance, **kwargs):
    """Track booking completion"""
    if instance.status == 'completed':
        event_id = f"booking_complete_{instance.id}_{uuid.uuid4().hex[:8]}"
        
        if not AnalyticsEvent.objects.filter(event_id=event_id).exists():
            AnalyticsEvent.objects.create(
                event_id=event_id,
                event_type='booking_completed',
                timestamp=timezone.now(),
                user=instance.user,
                data={
                    'booking_id': str(instance.id),
                    'reference': instance.booking_reference
                }
            )
            logger.info(f"Tracked booking completion for {instance.booking_reference}")

@receiver(post_save, sender=Payment)
def track_payment(sender, instance, created, **kwargs):
    """Track payment events - FIXED to prevent duplicates"""
    
    # Determine event type
    if created:
        event_type = 'payment_initiated'
    else:
        if instance.status == 'completed':
            event_type = 'payment_completed'
        elif instance.status == 'failed':
            event_type = 'payment_failed'
        elif instance.status == 'refunded':
            event_type = 'payment_refunded'
        else:
            return
    
    # Generate unique event ID with timestamp + UUID to prevent duplicates
    import time
    timestamp_ms = int(time.time() * 1000)
    event_id = f"payment_{instance.transaction_id}_{timestamp_ms}_{uuid.uuid4().hex[:4]}"
    
    # Check if event already exists
    if not AnalyticsEvent.objects.filter(event_id=event_id).exists():
        try:
            AnalyticsEvent.objects.create(
                event_id=event_id,
                event_type=event_type,
                timestamp=timezone.now(),
                user=instance.user,
                data={
                    'payment_id': str(instance.id),
                    'transaction_id': instance.transaction_id,
                    'amount': float(instance.amount_usd),
                    'method': instance.payment_method,
                    'status': instance.status
                }
            )
            logger.info(f"Tracked payment event {event_type} for {instance.transaction_id}")
        except Exception as e:
            logger.error(f"Failed to track payment event: {e}")

@receiver(post_save, sender=User)
def track_user_registration(sender, instance, created, **kwargs):
    """Track user registration"""
    if created:
        event_id = f"signup_{instance.id}_{uuid.uuid4().hex[:8]}"
        
        if not AnalyticsEvent.objects.filter(event_id=event_id).exists():
            AnalyticsEvent.objects.create(
                event_id=event_id,
                event_type='user_registered',
                timestamp=timezone.now(),
                user=instance,
                data={
                    'user_id': str(instance.id),
                    'email': instance.email,
                    'user_type': instance.user_type
                }
            )
            logger.info(f"Tracked user registration for {instance.email}")

# Keep existing handlers for DailyMetric
@receiver(post_save, sender=DailyMetric)
def check_metric_thresholds(sender, instance, **kwargs):
    """Check if metrics exceed thresholds"""
    if instance.revenue > 100000:
        logger.warning(f"High revenue alert: ${instance.revenue} on {instance.date}")
    if instance.total_bookings > 50:
        logger.info(f"High booking volume: {instance.total_bookings} on {instance.date}")
    if instance.payment_failed > 10:
        logger.error(f"High payment failure rate: {instance.payment_failed} failures on {instance.date}")

@receiver(pre_save, sender=DailyMetric)
def track_metric_changes(sender, instance, **kwargs):
    """Track significant changes in metrics"""
    if instance.pk:
        try:
            old = DailyMetric.objects.get(pk=instance.pk)
            
            changes = {}
            for field in ['revenue', 'total_bookings', 'new_users']:
                old_val = getattr(old, field, 0) or 0
                new_val = getattr(instance, field, 0) or 0
                
                if old_val > 0:
                    change_pct = ((new_val - old_val) / old_val) * 100
                    if abs(change_pct) > 20:
                        changes[field] = {
                            'old': float(old_val),
                            'new': float(new_val),
                            'change_pct': float(change_pct)
                        }
            
            if changes:
                logger.info(f"Significant metric changes detected for {instance.date}: {changes}")
        except DailyMetric.DoesNotExist:
            pass