from celery import shared_task
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from django.db import models  # Add this import
from .models import GeneratedDocument, DocumentSigning, DocumentArchive
from .generators import DocumentGenerator
import logging

logger = logging.getLogger(__name__)

@shared_task
def generate_document_pdf(document_id):
    """Generate PDF for document"""
    try:
        document = GeneratedDocument.objects.get(id=document_id)
        generator = DocumentGenerator(document)
        pdf_file = generator.generate_pdf()
        
        document.pdf_file.save(f"{document.document_number}.pdf", pdf_file)
        document.status = 'generated'
        document.save(update_fields=['pdf_file', 'status'])
        
        logger.info(f"PDF generated for document {document_id}")
        return True
    except GeneratedDocument.DoesNotExist:
        logger.error(f"Document {document_id} not found")
        return False

@shared_task
def send_document_email(document_id, email):
    """Send document via email"""
    try:
        document = GeneratedDocument.objects.get(id=document_id)
        
        subject = f"Your Document - {document.document_number}"
        message = f"""
        Dear {document.user.get_full_name() or document.user.email},
        
        Your document {document.document_number} is ready.
        
        You can view and download it here:
        {settings.SITE_URL}{document.get_absolute_url()}
        
        Best regards,
        FlynJet Team
        """
        
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [email],
            fail_silently=False,
        )
        
        document.status = 'sent'
        document.save(update_fields=['status'])
        
        logger.info(f"Document {document_id} sent to {email}")
        return True
    except GeneratedDocument.DoesNotExist:
        logger.error(f"Document {document_id} not found")
        return False

@shared_task
def check_expired_documents():
    """Check for expired documents"""
    expired = GeneratedDocument.objects.filter(
        expires_at__lt=timezone.now(),
        status__in=['generated', 'sent', 'viewed']
    )
    
    count = expired.update(status='expired')
    logger.info(f"Marked {count} documents as expired")
    return count

@shared_task
def archive_old_documents(days=365):
    """Archive documents older than specified days"""
    cutoff = timezone.now() - timezone.timedelta(days=days)
    old_docs = GeneratedDocument.objects.filter(
        created_at__lt=cutoff,
        status='downloaded'
    )
    
    archived_count = 0
    for doc in old_docs:
        try:
            # Create archive
            archive = DocumentArchive.objects.create(
                original_document=doc,
                archive_reason=f"Automatic archive after {days} days",
                retention_until=timezone.now() + timezone.timedelta(days=365*7),  # 7 years
                file_size=doc.pdf_file.size if doc.pdf_file else 0
            )
            
            # Copy file
            if doc.pdf_file:
                from django.core.files.base import ContentFile
                with open(doc.pdf_file.path, 'rb') as f:
                    archive.archived_file.save(
                        f"archive_{doc.document_number}.pdf",
                        ContentFile(f.read())
                    )
            
            # Delete original
            doc.delete()
            archived_count += 1
            
        except Exception as e:
            logger.error(f"Failed to archive document {doc.id}: {e}")
    
    logger.info(f"Archived {archived_count} documents")
    return archived_count

@shared_task
def send_signing_verification(signing_id):
    """Send verification code for document signing"""
    try:
        signing = DocumentSigning.objects.get(id=signing_id)
        signing.send_verification()
        logger.info(f"Verification sent for signing {signing_id}")
        return True
    except DocumentSigning.DoesNotExist:
        logger.error(f"Signing {signing_id} not found")
        return False

@shared_task
def cleanup_unsigned_documents(hours=24):
    """Delete unsigned draft documents"""
    cutoff = timezone.now() - timezone.timedelta(hours=hours)
    unsigned = GeneratedDocument.objects.filter(
        created_at__lt=cutoff,
        status='draft'
    )
    
    count = unsigned.count()
    unsigned.delete()
    
    logger.info(f"Cleaned up {count} unsigned draft documents")
    return count

@shared_task
def generate_document_report(days=30):
    """Generate document statistics report"""
    from django.db.models import Count, Sum  # Add this import here
    
    start_date = timezone.now() - timezone.timedelta(days=days)
    
    docs = GeneratedDocument.objects.filter(created_at__gte=start_date)
    
    # Fix the aggregation to avoid using models directly
    by_type = {}
    type_counts = docs.values('document_type').annotate(count=Count('id'))
    for item in type_counts:
        by_type[item['document_type']] = item['count']
    
    by_status = {}
    status_counts = docs.values('status').annotate(count=Count('id'))
    for item in status_counts:
        by_status[item['status']] = item['count']
    
    total_downloads = docs.aggregate(total=Sum('download_count'))['total'] or 0
    total_views = docs.aggregate(total=Sum('view_count'))['total'] or 0
    
    report = {
        'period_days': days,
        'total_documents': docs.count(),
        'by_type': by_type,
        'by_status': by_status,
        'total_downloads': total_downloads,
        'total_views': total_views,
        'signed_documents': docs.filter(is_signed=True).count(),
    }
    
    logger.info(f"Document report generated: {report}")
    return report