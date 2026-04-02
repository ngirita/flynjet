import uuid
from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.core.models import TimeStampedModel
from apps.accounts.models import User
from apps.bookings.models import Booking
from apps.payments.models import Payment

class Dispute(TimeStampedModel):
    """Customer disputes for bookings/payments"""
    
    DISPUTE_TYPES = (
        ('cancellation', 'Cancellation Dispute'),
        ('refund', 'Refund Dispute'),
        ('chargeback', 'Chargeback'),
        ('service', 'Service Quality'),
        ('billing', 'Billing Error'),
        ('damage', 'Damage Claim'),
        ('other', 'Other'),
    )
    
    DISPUTE_STATUS = (
        ('pending', 'Pending Review'),
        ('investigating', 'Under Investigation'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('escalated', 'Escalated'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
    )
    
    PRIORITY_LEVELS = (
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dispute_number = models.CharField(max_length=50, unique=True, db_index=True)
    
    # Relationships
    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name='disputes')
    booking = models.ForeignKey(Booking, on_delete=models.PROTECT, related_name='disputes')
    payment = models.ForeignKey(Payment, on_delete=models.SET_NULL, null=True, blank=True, related_name='disputes')
    
    # Dispute Details
    dispute_type = models.CharField(max_length=20, choices=DISPUTE_TYPES)
    status = models.CharField(max_length=20, choices=DISPUTE_STATUS, default='pending')
    priority = models.CharField(max_length=10, choices=PRIORITY_LEVELS, default='medium')
    
    # Amount
    disputed_amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')
    
    # Description
    subject = models.CharField(max_length=200)
    description = models.TextField()
    
    # Evidence
    evidence_files = models.JSONField(default=list, blank=True)
    
    # Timeline
    filed_at = models.DateTimeField(auto_now_add=True)
    response_deadline = models.DateTimeField()
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    # Assignment
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_disputes')
    assigned_at = models.DateTimeField(null=True, blank=True)
    
    # Resolution
    resolution_notes = models.TextField(blank=True)
    resolved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='resolved_disputes')
    
    # Outcome
    outcome = models.TextField(blank=True)
    refund_issued = models.BooleanField(default=False)
    refund_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    refund_transaction_id = models.CharField(max_length=200, blank=True)
    
    # Metadata
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-filed_at']
        indexes = [
            models.Index(fields=['dispute_number']),
            models.Index(fields=['user', '-filed_at']),
            models.Index(fields=['booking']),
            models.Index(fields=['status', 'priority']),
            models.Index(fields=['assigned_to', 'status']),
        ]
    
    def __str__(self):
        return f"Dispute {self.dispute_number} - {self.get_dispute_type_display()}"
    
    def save(self, *args, **kwargs):
        if not self.dispute_number:
            self.dispute_number = self.generate_dispute_number()
        if not self.response_deadline:
            self.response_deadline = timezone.now() + timezone.timedelta(days=7)
        super().save(*args, **kwargs)
    
    def generate_dispute_number(self):
        import random
        import string
        timestamp = timezone.now().strftime('%Y%m')
        random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        return f"DSP{timestamp}{random_str}"
    
    def assign_to(self, agent):
        """Assign dispute to agent"""
        self.assigned_to = agent
        self.assigned_at = timezone.now()
        self.status = 'investigating'
        self.save(update_fields=['assigned_to', 'assigned_at', 'status'])
        
        # Create notification
        from apps.core.models import Notification
        Notification.objects.create(
            recipient=agent,
            notification_type='dispute',
            title='New Dispute Assignment',
            message=f"Dispute {self.dispute_number} has been assigned to you",
            related_object=self
        )
    
    def add_evidence(self, file_url, description=""):
        """Add evidence file"""
        evidence = {
            'url': file_url,
            'description': description,
            'uploaded_at': timezone.now().isoformat()
        }
        self.evidence_files.append(evidence)
        self.save(update_fields=['evidence_files'])
    
    def resolve(self, resolution, outcome, resolved_by, refund_amount=0):
        """Resolve the dispute"""
        self.status = 'resolved'
        self.resolution_notes = resolution
        self.outcome = outcome
        self.resolved_by = resolved_by
        self.resolved_at = timezone.now()
        
        if refund_amount > 0:
            self.refund_issued = True
            self.refund_amount = refund_amount
        
        self.save(update_fields=[
            'status', 'resolution_notes', 'outcome', 
            'resolved_by', 'resolved_at', 'refund_issued', 'refund_amount'
        ])
        
        # Notify user
        from apps.core.models import Notification
        Notification.objects.create(
            recipient=self.user,
            notification_type='dispute',
            title='Dispute Resolved',
            message=f"Your dispute {self.dispute_number} has been resolved. Outcome: {outcome}",
            related_object=self
        )
    
    def escalate(self, reason):
        """Escalate dispute to higher level"""
        self.status = 'escalated'
        self.priority = 'high'
        self.save(update_fields=['status', 'priority'])
        
        # Notify admin
        from apps.core.models import Notification
        admin_users = User.objects.filter(user_type='admin')
        for admin in admin_users:
            Notification.objects.create(
                recipient=admin,
                notification_type='dispute',
                priority='high',
                title='Dispute Escalated',
                message=f"Dispute {self.dispute_number} escalated: {reason}",
                related_object=self
            )


class DisputeMessage(TimeStampedModel):
    """Messages within a dispute"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dispute = models.ForeignKey(Dispute, on_delete=models.CASCADE, related_name='messages')
    
    # Sender
    sender = models.ForeignKey(User, on_delete=models.PROTECT)
    is_staff = models.BooleanField(default=False)
    
    # Content
    message = models.TextField()
    attachment = models.FileField(upload_to='dispute_attachments/%Y/%m/%d/', blank=True)
    
    # Read Status
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['created_at']
    
    def __str__(self):
        return f"Message on {self.dispute.dispute_number} by {self.sender.email}"
    
    def mark_as_read(self, user):
        """Mark message as read"""
        if user != self.sender:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])


class DisputeEvidence(models.Model):
    """Evidence for disputes"""
    
    EVIDENCE_TYPES = (
        ('document', 'Document'),
        ('image', 'Image'),
        ('video', 'Video'),
        ('audio', 'Audio'),
        ('receipt', 'Receipt'),
        ('contract', 'Contract'),
        ('communication', 'Communication'),
        ('other', 'Other'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dispute = models.ForeignKey(Dispute, on_delete=models.CASCADE, related_name='evidence_items')
    
    evidence_type = models.CharField(max_length=20, choices=EVIDENCE_TYPES)
    file = models.FileField(upload_to='dispute_evidence/%Y/%m/%d/')
    description = models.TextField(blank=True)
    
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['uploaded_at']
    
    def __str__(self):
        return f"Evidence for {self.dispute.dispute_number}"


class DisputeResolution(TimeStampedModel):
    """Resolution options for disputes"""
    
    RESOLUTION_TYPES = (
        ('full_refund', 'Full Refund'),
        ('partial_refund', 'Partial Refund'),
        ('credit', 'Future Credit'),
        ('rebooking', 'Free Rebooking'),
        ('upgrade', 'Complimentary Upgrade'),
        ('apology', 'Formal Apology'),
        ('other', 'Other'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dispute = models.OneToOneField(Dispute, on_delete=models.CASCADE, related_name='resolution')
    
    resolution_type = models.CharField(max_length=20, choices=RESOLUTION_TYPES)
    description = models.TextField()
    
    # Financial Resolution
    refund_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    credit_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    credit_expiry = models.DateTimeField(null=True, blank=True)
    
    # Operational Resolution
    new_booking = models.ForeignKey(Booking, on_delete=models.SET_NULL, null=True, blank=True, related_name='dispute_resolution')
    
    # Acceptance
    accepted_by_customer = models.BooleanField(default=False)
    accepted_at = models.DateTimeField(null=True, blank=True)
    
    proposed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='proposed_resolutions')
    proposed_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['dispute', 'accepted_by_customer']),
        ]
    
    def __str__(self):
        return f"Resolution for {self.dispute.dispute_number}"
    
    def accept(self, customer):
        """Customer accepts resolution"""
        self.accepted_by_customer = True
        self.accepted_at = timezone.now()
        self.save(update_fields=['accepted_by_customer', 'accepted_at'])
        
        # Process resolution
        if self.resolution_type in ['full_refund', 'partial_refund'] and self.refund_amount > 0:
            # Process refund
            from apps.payments.models import Payment
            # Refund logic here
            
        elif self.resolution_type == 'credit' and self.credit_amount > 0:
            # Create credit
            from apps.accounts.models import UserCredit
            UserCredit.objects.create(
                user=customer,
                amount=self.credit_amount,
                expires_at=self.credit_expiry,
                source='dispute_resolution',
                source_id=str(self.id)
            )
        
        # Resolve dispute
        self.dispute.resolve(
            resolution=f"Resolution accepted: {self.get_resolution_type_display()}",
            outcome="Resolved via agreement",
            resolved_by=self.proposed_by,
            refund_amount=self.refund_amount
        )


class DisputeAnalytics(models.Model):
    """Analytics for dispute tracking"""
    
    date = models.DateField(db_index=True)
    
    # Volume Metrics
    total_disputes = models.IntegerField(default=0)
    open_disputes = models.IntegerField(default=0)
    resolved_disputes = models.IntegerField(default=0)
    escalated_disputes = models.IntegerField(default=0)
    
    # Financial Metrics
    total_disputed_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_refunded_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Resolution Metrics
    avg_resolution_time_hours = models.FloatField(default=0)
    customer_satisfaction_rate = models.FloatField(default=0)
    
    # Breakdown by Type
    disputes_by_type = models.JSONField(default=dict)
    disputes_by_status = models.JSONField(default=dict)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-date']
        unique_together = ['date']
    
    def __str__(self):
        return f"Dispute Analytics for {self.date}"