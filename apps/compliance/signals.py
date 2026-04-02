from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from .models import DataSubjectRequest, BreachNotification
from .gdpr import GDPRService
import logging

logger = logging.getLogger(__name__)

@receiver(post_save, sender=DataSubjectRequest)
def handle_dsr_creation(sender, instance, created, **kwargs):
    """Handle new data subject request"""
    if created:
        logger.info(f"New DSR created: {instance.request_number} - {instance.request_type}")
        
        # Send acknowledgment email
        from django.core.mail import send_mail
        
        send_mail(
            f"Your data request has been received - {instance.request_number}",
            f"""
            Dear {instance.requester_name},
            
            We have received your {instance.get_request_type_display()} request.
            Your request number is: {instance.request_number}
            
            We will process your request within 30 days as required by law.
            
            Best regards,
            FlynJet Compliance Team
            """,
            settings.DEFAULT_FROM_EMAIL,
            [instance.requester_email],
            fail_silently=False,
        )

@receiver(pre_save, sender=DataSubjectRequest)
def track_dsr_status_changes(sender, instance, **kwargs):
    """Track DSR status changes"""
    if instance.pk:
        try:
            old = DataSubjectRequest.objects.get(pk=instance.pk)
            if old.status != instance.status:
                logger.info(f"DSR {instance.request_number} status changed: {old.status} -> {instance.status}")
                
                # Send status update email
                if instance.status == 'completed':
                    from django.core.mail import send_mail
                    
                    send_mail(
                        f"Your data request has been completed - {instance.request_number}",
                        f"""
                        Dear {instance.requester_name},
                        
                        Your {instance.get_request_type_display()} request has been completed.
                        
                        You can view the results in your account or download the data here:
                        {settings.SITE_URL}{instance.response_file.url if instance.response_file else ''}
                        
                        Best regards,
                        FlynJet Compliance Team
                        """,
                        settings.DEFAULT_FROM_EMAIL,
                        [instance.requester_email],
                        fail_silently=False,
                    )
        except DataSubjectRequest.DoesNotExist:
            pass

@receiver(post_save, sender=BreachNotification)
def handle_breach_creation(sender, instance, created, **kwargs):
    """Handle new breach notification"""
    if created:
        logger.warning(f"New data breach recorded: {instance.breach_number} - Severity: {instance.severity}")
        
        # Alert compliance team
        from django.core.mail import send_mail
        from apps.accounts.models import User
        
        compliance_team = User.objects.filter(
            user_type='admin'
        ).values_list('email', flat=True)
        
        send_mail(
            f"URGENT: Data Breach Detected - {instance.breach_number}",
            f"""
            A new data breach has been detected:
            
            Breach ID: {instance.breach_number}
            Severity: {instance.get_severity_display()}
            Detected: {instance.detected_at}
            Description: {instance.description}
            Affected Users: {instance.affected_users_count}
            
            Please investigate immediately.
            """,
            settings.DEFAULT_FROM_EMAIL,
            compliance_team,
            fail_silently=False,
        )

@receiver(pre_save, sender=BreachNotification)
def track_breach_resolution(sender, instance, **kwargs):
    """Track breach resolution"""
    if instance.pk:
        try:
            old = BreachNotification.objects.get(pk=instance.pk)
            if old.status != instance.status and instance.status == 'resolved':
                logger.info(f"Breach {instance.breach_number} resolved")
                
                # Send resolution notification
                from django.core.mail import send_mail
                
                send_mail(
                    f"Breach Resolved - {instance.breach_number}",
                    f"""
                    Breach {instance.breach_number} has been resolved.
                    
                    Resolution: {instance.remediation_steps}
                    Resolved at: {instance.resolved_at}
                    
                    All necessary notifications have been sent.
                    """,
                    settings.DEFAULT_FROM_EMAIL,
                    [settings.ADMIN_EMAIL],
                    fail_silently=False,
                )
        except BreachNotification.DoesNotExist:
            pass