import json
from datetime import datetime, timedelta
from django.core.mail import send_mail
from django.conf import settings
from .models import ConsentRecord, DataSubjectRequest
import logging

logger = logging.getLogger(__name__)

class GDPRService:
    """GDPR compliance utilities"""
    
    @classmethod
    def check_consent(cls, user, consent_type):
        """Check if user has given consent"""
        latest = ConsentRecord.objects.filter(
            user=user,
            consent_type=consent_type
        ).order_by('-created_at').first()
        
        return latest.granted if latest else False
    
    @classmethod
    def get_consent_history(cls, user, consent_type=None):
        """Get consent history for user"""
        queryset = ConsentRecord.objects.filter(user=user)
        
        if consent_type:
            queryset = queryset.filter(consent_type=consent_type)
        
        return queryset.order_by('-created_at')
    
    @classmethod
    def process_data_export(cls, dsr):
        """Process data export request"""
        from apps.accounts.models import User
        from apps.bookings.models import Booking
        from apps.payments.models import Payment
        
        user = dsr.user
        
        # Collect all user data
        data = {
            'user': {
                'id': str(user.id),
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'date_joined': user.date_joined.isoformat(),
                'last_login': user.last_login.isoformat() if user.last_login else None,
                'user_type': user.user_type,
                'phone_number': str(user.phone_number) if user.phone_number else None,
            },
            'profile': {
                'nationality': user.profile.nationality if hasattr(user, 'profile') else None,
                'date_of_birth': user.profile.date_of_birth.isoformat() if hasattr(user, 'profile') and user.profile.date_of_birth else None,
            },
            'bookings': list(Booking.objects.filter(user=user).values()),
            'payments': list(Payment.objects.filter(user=user).values()),
            'consents': list(ConsentRecord.objects.filter(user=user).values()),
        }
        
        # Save to file
        import json
        import io
        from django.core.files.base import ContentFile
        
        json_data = json.dumps(data, indent=2, default=str)
        file = ContentFile(json_data.encode(), f"user_data_{user.id}.json")
        
        dsr.response_file.save(f"dsr_{dsr.request_number}.json", file)
        dsr.complete()
        
        # Notify user
        cls.send_data_export_notification(dsr)
        
        return dsr
    
    @classmethod
    def process_account_deletion(cls, dsr):
        """Process account deletion request"""
        from apps.accounts.models import User
        
        user = dsr.user
        
        # Anonymize user data
        user.email = f"deleted_{user.id}@deleted.flynjet.com"
        user.first_name = "Deleted"
        user.last_name = "User"
        user.is_active = False
        user.save()
        
        # Delete or anonymize related data
        # This is a simplified version - in production, you'd need to handle
        # all related models appropriately
        
        dsr.complete()
        
        # Send confirmation
        cls.send_deletion_confirmation(dsr)
        
        return dsr
    
    @classmethod
    def send_data_export_notification(cls, dsr):
        """Send notification that data is ready"""
        subject = "Your data export is ready"
        message = f"""
        Dear {dsr.requester_name},
        
        Your requested data export is now ready. You can download it here:
        {settings.SITE_URL}{dsr.response_file.url}
        
        This download link will expire in 7 days for security reasons.
        
        Best regards,
        FlynJet Compliance Team
        """
        
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [dsr.requester_email],
            fail_silently=False,
        )
    
    @classmethod
    def send_deletion_confirmation(cls, dsr):
        """Send confirmation of account deletion"""
        subject = "Account Deletion Confirmation"
        message = f"""
        Dear {dsr.requester_name},
        
        We confirm that your account has been deleted in accordance with your request.
        All your personal data has been removed from our systems.
        
        If you did not request this deletion, please contact us immediately.
        
        Best regards,
        FlynJet Compliance Team
        """
        
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [dsr.requester_email],
            fail_silently=False,
        )

class ConsentManager:
    """Manage user consent"""
    
    CONSENT_VERSIONS = {
        'terms': '2.1',
        'privacy': '3.0',
        'marketing': '1.5',
        'cookies': '2.0',
        'data_processing': '1.2'
    }
    
    @classmethod
    def get_current_version(cls, consent_type):
        """Get current version for consent type"""
        return cls.CONSENT_VERSIONS.get(consent_type, '1.0')
    
    @classmethod
    def needs_reconsent(cls, user, consent_type):
        """Check if user needs to give consent again due to version change"""
        latest = ConsentRecord.objects.filter(
            user=user,
            consent_type=consent_type
        ).order_by('-created_at').first()
        
        if not latest:
            return True
        
        current_version = cls.get_current_version(consent_type)
        return latest.version != current_version
    
    @classmethod
    def get_consent_summary(cls, user):
        """Get consent summary for user"""
        summary = {}
        
        for consent_type, _ in ConsentRecord.CONSENT_TYPES:
            latest = ConsentRecord.objects.filter(
                user=user,
                consent_type=consent_type
            ).order_by('-created_at').first()
            
            summary[consent_type] = {
                'granted': latest.granted if latest else False,
                'version': latest.version if latest else cls.get_current_version(consent_type),
                'date': latest.created_at if latest else None,
                'needs_update': cls.needs_reconsent(user, consent_type) if latest else True
            }
        
        return summary