# apps/documents/signals.py - FIXED VERSION

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from .models import GeneratedDocument, DocumentSigning
from apps.bookings.models import Booking
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=GeneratedDocument)
def document_created_handler(sender, instance, created, **kwargs):
    """Handle document creation"""
    if not hasattr(instance, 'document_number'):
        logger.warning(f"Instance is not a model instance: {type(instance)}")
        return
    
    if created:
        logger.info(f"Document {instance.document_number} created")
        
        try:
            from apps.core.models import Notification
            Notification.objects.create(
                recipient=instance.user,
                notification_type='document',
                title='Document Generated',
                message=f'Your document {instance.title} is ready.',
                related_object=instance,
                action_url=f"/documents/{instance.id}/"
            )
        except Exception as e:
            logger.error(f"Failed to create notification: {e}")


@receiver(post_save, sender=GeneratedDocument)
def update_document_stats(sender, instance, **kwargs):
    """Update document statistics when viewed or downloaded"""
    if not hasattr(instance, 'document_number'):
        logger.warning(f"Instance is not a model instance: {type(instance)}")
        return
    
    if hasattr(instance, 'tracker') and hasattr(instance.tracker, 'has_changed'):
        try:
            if instance.tracker.has_changed('view_count'):
                logger.info(f"Document {instance.document_number} viewed {instance.view_count} times")
            
            if instance.tracker.has_changed('download_count'):
                logger.info(f"Document {instance.document_number} downloaded {instance.download_count} times")
        except Exception as e:
            logger.error(f"Error checking tracker changes: {e}")
    else:
        if hasattr(instance, 'view_count') and instance.view_count:
            logger.info(f"Document {instance.document_number} view count: {instance.view_count}")
        if hasattr(instance, 'download_count') and instance.download_count:
            logger.info(f"Document {instance.document_number} download count: {instance.download_count}")


@receiver(post_save, sender=DocumentSigning)
def signing_created_handler(sender, instance, created, **kwargs):
    """Handle signing creation - VERIFICATION EMAIL REMOVED"""
    if not hasattr(instance, 'document'):
        logger.warning(f"Instance is not a model instance: {type(instance)}")
        return
    
    if created:
        logger.info(f"Signing request created for document {instance.document.document_number}")
        
        # VERIFICATION EMAIL REMOVED - No longer sends "Verify your signature" email
        
        # Notify document owner (optional - keep if you want notifications)
        try:
            from apps.core.models import Notification
            Notification.objects.create(
                recipient=instance.document.user,
                notification_type='document',
                title='Document Ready for Signature',
                message=f'Document {instance.document.title} requires your signature.',
                related_object=instance,
                action_url=f"/documents/sign/{instance.id}/"
            )
        except Exception as e:
            logger.error(f"Failed to create notification: {e}")


@receiver(pre_save, sender=DocumentSigning)
def signing_status_change(sender, instance, **kwargs):
    """Handle signing status changes"""
    if not hasattr(instance, 'document'):
        logger.warning(f"Instance is not a model instance: {type(instance)}")
        return
    
    if instance.pk:
        try:
            old = DocumentSigning.objects.get(pk=instance.pk)
            if old.status != instance.status:
                logger.info(f"Signing {instance.id} status changed: {old.status} -> {instance.status}")
                
                if instance.status == 'signed':
                    from apps.core.models import Notification
                    Notification.objects.create(
                        recipient=instance.document.user,
                        notification_type='document',
                        title='Document Signed',
                        message=f'Document {instance.document.title} has been signed.',
                        related_object=instance,
                        action_url=f"/documents/{instance.document.id}/"
                    )
        except DocumentSigning.DoesNotExist:
            pass
        except Exception as e:
            logger.error(f"Error checking signing status: {e}")


@receiver(post_save, sender=Booking)
def update_documents_on_payment_change(sender, instance, **kwargs):
    """Update document when booking payment status changes"""
    try:
        documents = GeneratedDocument.objects.filter(booking=instance)
        
        for doc in documents:
            # Update content_data with current payment status
            doc.content_data['payment_status'] = instance.payment_status
            doc.content_data['amount_paid'] = float(instance.amount_paid)
            doc.content_data['amount_due'] = float(instance.amount_due)
            doc.save()
            
            logger.info(f"Updated document {doc.document_number} payment status to {instance.payment_status}")
            
    except Exception as e:
        logger.error(f"Error updating documents for booking {instance.id}: {e}")


@receiver(post_save, sender=GeneratedDocument)
def generate_pdf_async(sender, instance, created, **kwargs):
    """Generate PDF asynchronously when document is created"""
    if not hasattr(instance, 'document_number'):
        logger.warning(f"Instance is not a model instance: {type(instance)}")
        return
    
    if created and not instance.pdf_file:
        try:
            from .tasks import generate_document_pdf
            generate_document_pdf.delay(instance.id)
            logger.info(f"Scheduled PDF generation for document {instance.document_number}")
        except Exception as e:
            logger.error(f"Failed to schedule PDF generation: {e}")


@receiver(pre_save, sender=GeneratedDocument)
def check_document_expiry(sender, instance, **kwargs):
    """Check if document is expired"""
    if not hasattr(instance, 'document_number'):
        logger.warning(f"Instance is not a model instance: {type(instance)}")
        return
    
    if instance.expires_at and instance.expires_at < timezone.now():
        if instance.status != 'expired':
            instance.status = 'expired'
            logger.info(f"Document {instance.document_number} expired")