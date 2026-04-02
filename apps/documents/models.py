import uuid
import hashlib
import logging
from django.db import models
from django.utils import timezone
from django.core.validators import FileExtensionValidator
from apps.core.models import TimeStampedModel
from apps.bookings.models import Booking, Invoice
from apps.accounts.models import User

logger = logging.getLogger(__name__)

class DocumentTemplate(TimeStampedModel):
    """Templates for document generation"""
    
    DOCUMENT_TYPES = (
        ('invoice', 'Invoice'),
        ('receipt', 'Receipt'),
        ('ticket', 'E-Ticket'),
        ('contract', 'Contract'),
        ('certificate', 'Certificate'),
        ('insurance', 'Insurance Certificate'),
        ('customs', 'Customs Form'),
        ('boarding_pass', 'Boarding Pass'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPES)
    template_file = models.FileField(
        upload_to='document_templates/',
        validators=[FileExtensionValidator(['html', 'pdf', 'docx'])]
    )
    
    # Template Configuration
    variables = models.JSONField(default=list, help_text="List of available variables")
    styles = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    
    # Version Control
    version = models.CharField(max_length=20)
    previous_version = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True)
    
    # Metadata
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    class Meta:
        ordering = ['-created_at']
        unique_together = ['document_type', 'version']
    
    def __str__(self):
        return f"{self.get_document_type_display()} - {self.name} v{self.version}"


class GeneratedDocument(TimeStampedModel):
    """Generated documents for bookings/users"""
    
    DOCUMENT_STATUS = (
        ('draft', 'Draft'),
        ('generated', 'Generated'),
        ('sent', 'Sent'),
        ('viewed', 'Viewed'),
        ('downloaded', 'Downloaded'),
        ('expired', 'Expired'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document_number = models.CharField(max_length=100, unique=True, db_index=True)
    
    # Relationships
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='documents')
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, null=True, blank=True, related_name='documents')
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, null=True, blank=True, related_name='documents')
    template = models.ForeignKey(
        DocumentTemplate, 
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='generated_documents'
    )
    
    # Document Details
    document_type = models.CharField(max_length=20, choices=DocumentTemplate.DOCUMENT_TYPES)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    # File
    pdf_file = models.FileField(upload_to='documents/%Y/%m/%d/')
    html_file = models.FileField(upload_to='documents/html/%Y/%m/%d/', blank=True)
    file_size = models.IntegerField(default=0)
    
    # Content
    content_data = models.JSONField(default=dict, help_text="Data used to generate document")
    
    # Security
    access_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    access_password = models.CharField(max_length=128, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=DOCUMENT_STATUS, default='generated')
    is_signed = models.BooleanField(default=False)
    signed_at = models.DateTimeField(null=True, blank=True)
    
    # Tracking
    viewed_at = models.DateTimeField(null=True, blank=True)
    downloaded_at = models.DateTimeField(null=True, blank=True)
    view_count = models.IntegerField(default=0)
    download_count = models.IntegerField(default=0)
    
    # Metadata
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    # Add tracker property here
    @property
    def tracker(self):
        """Return tracker data for compatibility with existing code"""
        return {
            'view_count': self.view_count,
            'download_count': self.download_count,
            'viewed_at': self.viewed_at,
            'downloaded_at': self.downloaded_at,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent
        }
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['document_number']),
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['booking', 'document_type']),
            models.Index(fields=['access_token']),
            models.Index(fields=['expires_at']),
        ]
    
    def __str__(self):
        return f"{self.document_number} - {self.title}"
    
    def save(self, *args, **kwargs):
        if not self.document_number:
            self.document_number = self.generate_document_number()
        super().save(*args, **kwargs)
    
    def generate_document_number(self):
        """Generate unique document number"""
        import random
        import string
        prefix = dict(DocumentTemplate.DOCUMENT_TYPES).get(self.document_type, 'DOC')[:3].upper()
        timestamp = timezone.now().strftime('%Y%m')
        random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        return f"{prefix}{timestamp}{random_str}"
    
    def record_view(self, request=None):
        """Record document view"""
        self.status = 'viewed'
        self.viewed_at = timezone.now()
        self.view_count += 1
        if request:
            self.ip_address = self.get_client_ip(request)
            self.user_agent = request.META.get('HTTP_USER_AGENT', '')
        self.save(update_fields=['status', 'viewed_at', 'view_count', 'ip_address', 'user_agent'])
    
    def record_download(self):
        """Record document download"""
        self.status = 'downloaded'
        self.downloaded_at = timezone.now()
        self.download_count += 1
        self.save(update_fields=['status', 'downloaded_at', 'download_count'])
    
    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def is_valid(self):
        """Check if document is still valid"""
        if self.expires_at and timezone.now() > self.expires_at:
            return False
        return True
    
    def generate_access_link(self):
        """Generate secure access link"""
        return f"/documents/access/{self.access_token}/"

    # Add this method inside the GeneratedDocument class, before the closing class bracket

    def regenerate_pdf(self):
        """Regenerate PDF with current booking data"""
        from io import BytesIO
        from django.template.loader import render_to_string
        from weasyprint import HTML
        from django.core.files.base import ContentFile
        
        if not self.booking:
            return False
        
        booking = self.booking
        
        # ============ GET PAYMENT INFO FROM COMPLETED PAYMENT ============
        completed_payment = booking.payments.filter(status='completed').first()
        
        payment_info = {
            'method': 'Not paid yet',
            'transaction_id': 'N/A',
            'date': None,
            'status': booking.payment_status,
        }
        
        if completed_payment:
            payment_info = {
                'method': completed_payment.get_payment_method_display(),
                'transaction_id': completed_payment.transaction_id,
                'date': completed_payment.payment_date,
                'status': 'paid',
            }
        # ================================================================
        
        # ============ UPDATED TEMPLATE MAP ============
        template_map = {
            'invoice': 'invoices/standard.html',
            'corporate': 'invoices/corporate.html',
            'proforma': 'invoices/proforma.html',
            'ticket': 'tickets/e_ticket.html',
            'boarding_pass': 'tickets/boarding_pass.html',
        }
        # ==============================================
        
        template_name = template_map.get(self.document_type, 'invoices/standard.html')

        
        context = {
            'booking': {
                'booking_reference': booking.booking_reference,
                'departure_airport': booking.departure_airport,
                'arrival_airport': booking.arrival_airport,
                'departure_datetime': booking.departure_datetime,
                'arrival_datetime': booking.arrival_datetime,
                'passenger_count': booking.passenger_count,
                'total_amount_usd': float(booking.total_amount_usd),
                'base_price_usd': float(booking.base_price_usd),
                'fuel_surcharge_usd': float(booking.fuel_surcharge_usd),
                'handling_fee_usd': float(booking.handling_fee_usd),
                'catering_cost_usd': float(booking.catering_cost_usd),
                'cleaning_charge_usd': float(booking.cleaning_charge_usd),
                'tax_amount_usd': float(booking.tax_amount_usd),
                'discount_amount_usd': float(booking.discount_amount_usd),
                'amount_paid': float(booking.amount_paid),
                'amount_due': float(booking.amount_due),
                'status': booking.status,
                'payment_status': booking.payment_status,
                'flight_type': booking.flight_type,
                'created_at': booking.created_at,
            },
            'user': {
                'first_name': booking.user.first_name,
                'last_name': booking.user.last_name,
                'email': booking.user.email,
                'phone_number': str(getattr(booking.user, 'phone_number', '')),
            },
            'document': {
                'document_number': self.document_number,
                'created_at': self.created_at,
                'total_usd': float(booking.total_amount_usd),
                'amount_paid': float(booking.amount_paid),
                'amount_due': float(booking.amount_due),
                'payment_status': booking.payment_status,
                # ============ ADD PAYMENT INFO FOR TEMPLATES ============
                'payment_method': payment_info['method'],
                'payment_transaction_id': payment_info['transaction_id'],
                'payment_date': payment_info['date'],
                'status': payment_info['status'],
                # ========================================================
            },
            'doc_type': self.document_type,
            'company': {
                'name': 'FlynJet Air and Logistics.',
                'address': 'Jomo Kenyatta International Airport. Airport Nort Road, Embakasi',
                'city': 'Miami',
                'state': 'FL',
                'postal_code': '19087-00501',
                'country': 'Kenya',
                'phone': '+254785651832',
                'whatsapp': '+447393700477',
                'email': 'info@flynjet.com',
                'tax_id': '12-3456789',
            }
        }
        
        try:
            html_content = render_to_string(template_name, context)
            pdf_file = BytesIO()
            HTML(string=html_content).write_pdf(pdf_file)
            pdf_file.seek(0)
            
            filename = f"{self.document_type}_{booking.booking_reference}.pdf"
            self.pdf_file.save(filename, ContentFile(pdf_file.getvalue()))
            
            # Save payment info to content_data for future reference
            self.content_data['payment_status'] = booking.payment_status
            self.content_data['amount_paid'] = float(booking.amount_paid)
            self.content_data['amount_due'] = float(booking.amount_due)
            self.content_data['payment_method'] = payment_info['method']
            self.content_data['payment_transaction_id'] = payment_info['transaction_id']
            self.content_data['payment_date'] = payment_info['date'].isoformat() if payment_info['date'] else None
            self.save()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to regenerate PDF for {self.document_number}: {e}")
            return False
            
    def verify_password(self, password):
        """Verify access password"""
        if not self.access_password:
            return True
        from django.contrib.auth.hashers import check_password
        return check_password(password, self.access_password)

class DocumentSigning(TimeStampedModel):
    """Digital signing of documents"""
    
    SIGNING_METHODS = (
        ('electronic', 'Electronic Signature'),
        ('digital', 'Digital Certificate'),
        ('biometric', 'Biometric'),
        ('sms', 'SMS Verification'),
        ('email', 'Email Verification'),
    )
    
    SIGNING_STATUS = (
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('viewed', 'Viewed'),
        ('signed', 'Signed'),
        ('declined', 'Declined'),
        ('expired', 'Expired'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(GeneratedDocument, on_delete=models.CASCADE, related_name='signatures')
    
    # Signer
    signer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='document_signatures')
    signer_email = models.EmailField()
    signer_name = models.CharField(max_length=200)
    
    # Signing Details
    signing_method = models.CharField(max_length=20, choices=SIGNING_METHODS)
    status = models.CharField(max_length=20, choices=SIGNING_STATUS, default='pending')
    
    # Signature Data
    signature_data = models.TextField(blank=True, help_text="Base64 encoded signature image")
    signature_hash = models.CharField(max_length=128, blank=True)
    certificate_info = models.JSONField(default=dict, blank=True)
    
    # Verification
    verification_code = models.CharField(max_length=10, blank=True)
    verification_sent_at = models.DateTimeField(null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    
    # IP and Location
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    location = models.CharField(max_length=255, blank=True)
    user_agent = models.TextField(blank=True)
    
    # Expiry
    expires_at = models.DateTimeField()
    
    class Meta:
        ordering = ['-created_at']
        unique_together = ['document', 'signer']
    
    def __str__(self):
        return f"Signature for {self.document.document_number} by {self.signer_email}"
    
    def send_verification(self):
        """Send verification code"""
        import random
        self.verification_code = ''.join(random.choices('0123456789', k=6))
        self.verification_sent_at = timezone.now()
        self.save(update_fields=['verification_code', 'verification_sent_at'])
        
        # Send email with code
        from django.core.mail import send_mail
        send_mail(
            f"Verify your signature for {self.document.document_number}",
            f"Your verification code is: {self.verification_code}",
            'info@flynjet.com',
            [self.signer_email],
            fail_silently=False,
        )
    
    def verify(self, code, request=None):
        """Verify signature with code"""
        if self.verification_code != code:
            return False
        
        if self.expires_at and timezone.now() > self.expires_at:
            self.status = 'expired'
            self.save(update_fields=['status'])
            return False
        
        self.status = 'signed'
        self.verified_at = timezone.now()
        if request:
            self.ip_address = self.get_client_ip(request)
            self.user_agent = request.META.get('HTTP_USER_AGENT', '')
        self.save(update_fields=['status', 'verified_at', 'ip_address', 'user_agent'])
        
        # Update document
        self.document.is_signed = True
        self.document.signed_at = timezone.now()
        self.document.save(update_fields=['is_signed', 'signed_at'])
        
        return True
    
    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class DocumentArchive(TimeStampedModel):
    """Archived documents for long-term storage"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    original_document = models.OneToOneField(GeneratedDocument, on_delete=models.SET_NULL, null=True)
    
    # Archive Information
    archive_reference = models.CharField(max_length=100, unique=True)
    archive_date = models.DateTimeField(auto_now_add=True)
    archive_reason = models.CharField(max_length=200)
    
    # File
    archived_file = models.FileField(upload_to='archives/%Y/%m/')
    file_hash = models.CharField(max_length=128)
    file_size = models.IntegerField()
    
    # Retention
    retention_until = models.DateTimeField()
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['archive_reference']),
            models.Index(fields=['retention_until']),
        ]
    
    def __str__(self):
        return f"Archive {self.archive_reference}"
    
    def calculate_file_hash(self):
        """Calculate SHA-256 hash of file"""
        if self.archived_file:
            sha256 = hashlib.sha256()
            for chunk in self.archived_file.chunks():
                sha256.update(chunk)
            return sha256.hexdigest()
        return None