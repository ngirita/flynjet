from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from .models import Dispute, DisputeMessage, DisputeResolution
from .notifications import DisputeNotificationService
import logging

logger = logging.getLogger(__name__)

@receiver(post_save, sender=Dispute)
def dispute_created_handler(sender, instance, created, **kwargs):
    """Handle new dispute creation"""
    if created:
        # Send notification to admins
        DisputeNotificationService.notify_dispute_filed(instance)
        
        # Update analytics
        from .models import DisputeAnalytics
        today = timezone.now().date()
        analytics, _ = DisputeAnalytics.objects.get_or_create(date=today)
        analytics.total_disputes += 1
        analytics.open_disputes += 1
        analytics.total_disputed_amount += instance.disputed_amount
        analytics.save()
        
        logger.info(f"Dispute {instance.dispute_number} created")

@receiver(pre_save, sender=Dispute)
def dispute_status_change_handler(sender, instance, **kwargs):
    """Handle dispute status changes"""
    if instance.pk:
        try:
            old = Dispute.objects.get(pk=instance.pk)
            if old.status != instance.status:
                # Notify user of status change
                DisputeNotificationService.notify_status_change(instance, old.status)
                
                # Update analytics
                from .models import DisputeAnalytics
                today = timezone.now().date()
                analytics, _ = DisputeAnalytics.objects.get_or_create(date=today)
                
                if instance.status == 'resolved':
                    analytics.resolved_disputes += 1
                    analytics.open_disputes -= 1
                    
                    # Calculate resolution time
                    if instance.resolved_at and instance.filed_at:
                        hours = (instance.resolved_at - instance.filed_at).total_seconds() / 3600
                        # Update average resolution time
                        total_hours = analytics.avg_resolution_time_hours * (analytics.resolved_disputes - 1)
                        analytics.avg_resolution_time_hours = (total_hours + hours) / analytics.resolved_disputes
                
                elif instance.status == 'escalated':
                    analytics.escalated_disputes += 1
                
                analytics.save()
                
                logger.info(f"Dispute {instance.dispute_number} status changed: {old.status} -> {instance.status}")
        except Dispute.DoesNotExist:
            pass

@receiver(post_save, sender=DisputeMessage)
def dispute_message_handler(sender, instance, created, **kwargs):
    """Handle new dispute messages"""
    if created:
        # Notify recipient
        DisputeNotificationService.notify_new_message(instance)
        
        # Update dispute
        dispute = instance.dispute
        dispute.updated_at = timezone.now()
        dispute.save(update_fields=['updated_at'])
        
        logger.info(f"New message on dispute {dispute.dispute_number}")

@receiver(post_save, sender=DisputeResolution)
def dispute_resolution_handler(sender, instance, created, **kwargs):
    """Handle dispute resolution proposals"""
    if created:
        # Notify customer
        DisputeNotificationService.notify_resolution_proposed(instance.dispute, instance)
        logger.info(f"Resolution proposed for dispute {instance.dispute.dispute_number}")

@receiver(pre_save, sender=DisputeResolution)
def resolution_accepted_handler(sender, instance, **kwargs):
    """Handle resolution acceptance"""
    if instance.pk:
        try:
            old = DisputeResolution.objects.get(pk=instance.pk)
            if not old.accepted_by_customer and instance.accepted_by_customer:
                # Resolution accepted
                DisputeNotificationService.notify_resolution_accepted(instance.dispute)
                
                # Update dispute
                dispute = instance.dispute
                dispute.status = 'resolved'
                dispute.resolved_at = timezone.now()
                dispute.save(update_fields=['status', 'resolved_at'])
                
                logger.info(f"Resolution accepted for dispute {dispute.dispute_number}")
        except DisputeResolution.DoesNotExist:
            pass

@receiver(post_save, sender=Dispute)
def check_escalation(sender, instance, **kwargs):
    """Check if dispute needs escalation"""
    from .workflows import DisputeEscalationMatrix
    
    if instance.status in ['pending', 'investigating']:
        should_escalate, reason = DisputeEscalationMatrix.should_escalate(instance)
        if should_escalate and instance.status != 'escalated':
            instance.escalate(reason)
            logger.info(f"Dispute {instance.dispute_number} auto-escalated: {reason}")

@receiver(post_save, sender=Dispute)
def update_customer_status(sender, instance, **kwargs):
    """Update customer status based on dispute history"""
    if instance.status == 'resolved' and instance.refund_issued:
        user = instance.user
        
        # Track dispute history
        dispute_count = Dispute.objects.filter(user=user, status='resolved').count()
        
        if dispute_count >= 3:
            # Flag customer for review
            user.metadata['dispute_flag'] = True
            user.metadata['dispute_count'] = dispute_count
            user.save(update_fields=['metadata'])
            
            logger.warning(f"Customer {user.email} has {dispute_count} resolved disputes")