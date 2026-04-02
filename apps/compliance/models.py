import uuid
from django.db import models
from django.utils import timezone
from apps.core.models import TimeStampedModel
from apps.accounts.models import User

class ConsentRecord(TimeStampedModel):
    """User consent records for GDPR/compliance"""
    
    CONSENT_TYPES = (
        ('terms', 'Terms of Service'),
        ('privacy', 'Privacy Policy'),
        ('marketing', 'Marketing Communications'),
        ('cookies', 'Cookie Consent'),
        ('data_processing', 'Data Processing'),
        ('third_party', 'Third Party Sharing'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='consent_records')
    
    # Consent Details
    consent_type = models.CharField(max_length=20, choices=CONSENT_TYPES)
    version = models.CharField(max_length=20)
    granted = models.BooleanField(default=True)
    
    # IP and Location
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    
    # Document
    document_url = models.URLField(blank=True)
    
    # Withdrawal
    withdrawn_at = models.DateTimeField(null=True, blank=True)
    withdrawal_ip = models.GenericIPAddressField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'consent_type']),
            models.Index(fields=['-created_at']),
        ]
    
    def __str__(self):
        status = "Granted" if self.granted else "Withdrawn"
        return f"{self.get_consent_type_display()} {status} by {self.user.email}"
    
    def withdraw(self, ip_address=None):
        """Withdraw consent"""
        self.granted = False
        self.withdrawn_at = timezone.now()
        self.withdrawal_ip = ip_address
        self.save(update_fields=['granted', 'withdrawn_at', 'withdrawal_ip'])


class DataProcessingAgreement(TimeStampedModel):
    """Data processing agreements with third parties"""
    
    AGREEMENT_TYPES = (
        ('processor', 'Data Processor'),
        ('controller', 'Data Controller'),
        ('subprocessor', 'Sub-processor'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agreement_number = models.CharField(max_length=50, unique=True)
    
    # Third Party
    company_name = models.CharField(max_length=200)
    contact_name = models.CharField(max_length=200)
    contact_email = models.EmailField()
    contact_phone = models.CharField(max_length=50, blank=True)
    
    # Agreement Details
    agreement_type = models.CharField(max_length=20, choices=AGREEMENT_TYPES)
    purpose = models.TextField()
    data_categories = models.JSONField(default=list)
    
    # Dates
    signed_date = models.DateField()
    effective_date = models.DateField()
    expiry_date = models.DateField()
    
    # Security
    security_measures = models.TextField()
    breach_notification_time = models.IntegerField(help_text="Hours to notify of breach")
    
    # Documents
    agreement_file = models.FileField(upload_to='compliance/dpa/')
    
    # Status
    is_active = models.BooleanField(default=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['agreement_number']),
            models.Index(fields=['expiry_date']),
        ]
    
    def __str__(self):
        return f"DPA with {self.company_name} ({self.get_agreement_type_display()})"
    
    def is_expiring_soon(self, days=30):
        """Check if agreement is expiring soon"""
        if self.expiry_date:
            days_until = (self.expiry_date - timezone.now().date()).days
            return 0 < days_until <= days
        return False


class DataSubjectRequest(TimeStampedModel):
    """GDPR/CCPA data subject requests"""
    
    REQUEST_TYPES = (
        ('access', 'Right to Access'),
        ('rectification', 'Right to Rectification'),
        ('erasure', 'Right to Erasure'),
        ('restriction', 'Right to Restriction'),
        ('portability', 'Right to Data Portability'),
        ('objection', 'Right to Object'),
    )
    
    REQUEST_STATUS = (
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('rejected', 'Rejected'),
        ('expired', 'Expired'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request_number = models.CharField(max_length=50, unique=True)
    
    # Requester
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    requester_email = models.EmailField()
    requester_name = models.CharField(max_length=200)
    
    # Request Details
    request_type = models.CharField(max_length=20, choices=REQUEST_TYPES)
    status = models.CharField(max_length=20, choices=REQUEST_STATUS, default='pending')
    description = models.TextField()
    
    # Verification
    verification_method = models.CharField(max_length=100)
    verified_at = models.DateTimeField(null=True, blank=True)
    
    # Timeline
    submitted_at = models.DateTimeField(auto_now_add=True)
    deadline = models.DateTimeField()
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Response
    response_file = models.FileField(upload_to='compliance/dsr/%Y/%m/', blank=True)
    response_notes = models.TextField(blank=True)
    
    # Processor
    processed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='processed_requests')
    
    class Meta:
        ordering = ['-submitted_at']
        indexes = [
            models.Index(fields=['request_number']),
            models.Index(fields=['status', 'deadline']),
        ]
    
    def __str__(self):
        return f"DSR {self.request_number} - {self.get_request_type_display()}"
    
    def save(self, *args, **kwargs):
        if not self.request_number:
            self.request_number = self.generate_request_number()
        if not self.deadline:
            # 30 days by default for GDPR
            self.deadline = timezone.now() + timezone.timedelta(days=30)
        super().save(*args, **kwargs)
    
    def generate_request_number(self):
        import random
        import string
        timestamp = timezone.now().strftime('%Y%m')
        random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        return f"DSR{timestamp}{random_str}"
    
    def process(self, processor):
        """Start processing the request"""
        self.status = 'processing'
        self.processed_by = processor
        self.save(update_fields=['status', 'processed_by'])
    
    def complete(self, response_file=None, notes=""):
        """Complete the request"""
        self.status = 'completed'
        self.completed_at = timezone.now()
        if response_file:
            self.response_file = response_file
        if notes:
            self.response_notes = notes
        self.save(update_fields=['status', 'completed_at', 'response_file', 'response_notes'])
        
        # Notify requester
        self.send_completion_notification()
    
    def reject(self, reason):
        """Reject the request"""
        self.status = 'rejected'
        self.response_notes = reason
        self.save(update_fields=['status', 'response_notes'])
    
    def send_completion_notification(self):
        """Send completion notification"""
        from django.core.mail import send_mail
        
        subject = f"Your Data Request {self.request_number} has been completed"
        message = f"""
        Dear {self.requester_name},
        
        Your data subject request ({self.get_request_type_display()}) has been completed.
        
        Request Number: {self.request_number}
        Completed: {self.completed_at}
        
        You can download your data here: {self.response_file.url if self.response_file else 'N/A'}
        
        If you have any questions, please contact our Data Protection Officer at info@flynjet.com.
        
        Best regards,
        FlynJet Compliance Team
        """
        
        send_mail(
            subject,
            message,
            'info@flynjet.com',
            [self.requester_email],
            fail_silently=False,
        )


class BreachNotification(TimeStampedModel):
    """Data breach notifications"""
    
    SEVERITY_LEVELS = (
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    )
    
    NOTIFICATION_STATUS = (
        ('detected', 'Detected'),
        ('investigating', 'Investigating'),
        ('contained', 'Contained'),
        ('notified', 'Notified'),
        ('resolved', 'Resolved'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    breach_number = models.CharField(max_length=50, unique=True)
    
    # Breach Details
    detected_at = models.DateTimeField()
    severity = models.CharField(max_length=20, choices=SEVERITY_LEVELS)
    status = models.CharField(max_length=20, choices=NOTIFICATION_STATUS, default='detected')
    
    # Description
    description = models.TextField()
    affected_data = models.JSONField(default=list)
    affected_users_count = models.IntegerField(default=0)
    
    # Investigation
    root_cause = models.TextField(blank=True)
    impact_assessment = models.TextField(blank=True)
    
    # Notification
    notified_authorities = models.BooleanField(default=False)
    authorities_notified_at = models.DateTimeField(null=True, blank=True)
    notified_users = models.BooleanField(default=False)
    users_notified_at = models.DateTimeField(null=True, blank=True)
    
    # Remediation
    remediation_steps = models.TextField(blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-detected_at']
        indexes = [
            models.Index(fields=['breach_number']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"Breach {self.breach_number} - {self.get_severity_display()}"
    
    def save(self, *args, **kwargs):
        if not self.breach_number:
            self.breach_number = self.generate_breach_number()
        super().save(*args, **kwargs)
    
    def generate_breach_number(self):
        import random
        import string
        timestamp = timezone.now().strftime('%Y%m%d')
        random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
        return f"BR{timestamp}{random_str}"
    
    def notify_authorities(self):
        """Notify relevant authorities of breach"""
        # This would integrate with relevant data protection authorities
        self.notified_authorities = True
        self.authorities_notified_at = timezone.now()
        self.save(update_fields=['notified_authorities', 'authorities_notified_at'])
    
    def notify_affected_users(self):
        """Notify affected users of breach"""
        from django.core.mail import send_mail
        
        subject = f"Security Notice: Data Breach {self.breach_number}"
        message = f"""
        Dear Customer,
        
        We are writing to inform you of a data security incident that may affect your personal data.
        
        Breach ID: {self.breach_number}
        Detected: {self.detected_at}
        
        What happened: {self.description}
        
        Data affected: {', '.join(self.affected_data)}
        
        What we are doing: {self.remediation_steps}
        
        We take your privacy seriously and apologize for any concern this may cause.
        
        If you have questions, please contact our Data Protection Officer at info@flynjet.com.
        
        Best regards,
        FlynJet Security Team
        """
        
        # In production, this would be batched and sent to affected users only
        # For now, we'll just mark as notified
        self.notified_users = True
        self.users_notified_at = timezone.now()
        self.save(update_fields=['notified_users', 'users_notified_at'])
    
    def resolve(self, remediation):
        """Mark breach as resolved"""
        self.status = 'resolved'
        self.remediation_steps = remediation
        self.resolved_at = timezone.now()
        self.save(update_fields=['status', 'remediation_steps', 'resolved_at'])