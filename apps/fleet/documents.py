from django.db import models
from django.utils import timezone
from datetime import timedelta  # Add this import
from django.conf import settings  # Add this import
from .models import Aircraft, AircraftDocument
import logging

logger = logging.getLogger(__name__)

class DocumentManager:
    """Manage aircraft documents"""
    
    @classmethod
    def get_expiring_documents(cls, days=30):
        """Get documents expiring within specified days"""
        expiry_threshold = timezone.now().date() + timedelta(days=days)
        
        return AircraftDocument.objects.filter(
            expiry_date__lte=expiry_threshold,
            expiry_date__gte=timezone.now().date(),
            is_approved=True
        ).select_related('aircraft')
    
    @classmethod
    def get_expired_documents(cls):
        """Get expired documents"""
        return AircraftDocument.objects.filter(
            expiry_date__lt=timezone.now().date(),
            is_approved=True
        ).select_related('aircraft')
    
    @classmethod
    def get_aircraft_document_status(cls, aircraft_id):
        """Get document status summary for aircraft"""
        documents = AircraftDocument.objects.filter(aircraft_id=aircraft_id)
        
        total = documents.count()
        valid = documents.filter(expiry_date__gte=timezone.now().date(), is_approved=True).count()
        expiring = documents.filter(
            expiry_date__lte=timezone.now().date() + timedelta(days=30),
            expiry_date__gte=timezone.now().date()
        ).count()
        expired = documents.filter(expiry_date__lt=timezone.now().date()).count()
        
        return {
            'total': total,
            'valid': valid,
            'expiring_soon': expiring,
            'expired': expired,
            'compliance_rate': (valid / total * 100) if total > 0 else 0
        }
    
    @classmethod
    def send_document_reminders(cls):
        """Send reminders for expiring documents"""
        from django.core.mail import send_mail
        
        expiring = cls.get_expiring_documents(30)
        
        for doc in expiring:
            days_left = (doc.expiry_date - timezone.now().date()).days
            
            subject = f"Document Expiring Soon - {doc.aircraft.registration_number}"
            message = f"""
            The following document will expire in {days_left} days:
            
            Aircraft: {doc.aircraft.registration_number}
            Document: {doc.title}
            Type: {doc.get_document_type_display()}
            Number: {doc.document_number}
            Expiry Date: {doc.expiry_date}
            
            Please renew as soon as possible.
            """
            
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [settings.DOCUMENTS_TEAM_EMAIL],
                fail_silently=False,
            )
            
            logger.info(f"Reminder sent for document {doc.id}")
        
        return expiring.count()

class DocumentTemplate(models.Model):
    """Templates for aircraft documents"""
    
    DOCUMENT_TYPES = (
        ('certificate', 'Certificate'),
        ('manual', 'Manual'),
        ('logbook', 'Logbook'),
        ('insurance', 'Insurance'),
        ('warranty', 'Warranty'),
        ('technical', 'Technical Document'),
        ('legal', 'Legal Document'),
    )
    
    name = models.CharField(max_length=200)
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPES)
    template_file = models.FileField(upload_to='document_templates/')
    
    # Template fields
    fields = models.JSONField(default=list)  # List of required fields
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.name} ({self.get_document_type_display()})"

class DocumentChecklist(models.Model):
    """Checklist of required documents by aircraft type"""
    
    aircraft_type = models.CharField(max_length=100)  # e.g., "Boeing 737"
    documents_required = models.JSONField(default=list)  # List of required document types
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Document Checklist - {self.aircraft_type}"
    
    def check_compliance(self, aircraft_id):
        """Check if aircraft has all required documents"""
        aircraft = Aircraft.objects.get(id=aircraft_id)
        existing_docs = set(
            aircraft.documents.filter(
                document_type__in=self.documents_required,
                expiry_date__gte=timezone.now().date(),
                is_approved=True
            ).values_list('document_type', flat=True)
        )
        
        required = set(self.documents_required)
        missing = required - existing_docs
        
        return {
            'compliant': len(missing) == 0,
            'missing_documents': list(missing),
            'compliance_percentage': (len(existing_docs) / len(required) * 100) if required else 100
        }

class DocumentAudit(models.Model):
    """Audit trail for document changes"""
    
    document = models.ForeignKey(AircraftDocument, on_delete=models.CASCADE, related_name='audits')
    action = models.CharField(max_length=50)  # created, updated, approved, rejected, expired
    user = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True)
    
    changes = models.JSONField(default=dict)  # Track what changed
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.document} - {self.action} at {self.timestamp}"
    
    @classmethod
    def log_change(cls, document, action, user, changes=None):
        """Log document change"""
        cls.objects.create(
            document=document,
            action=action,
            user=user,
            changes=changes or {}
        )
        logger.info(f"Document {document.id} - {action} by {user.email if user else 'system'}")