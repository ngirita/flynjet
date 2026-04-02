import uuid
from django.db import models
from django.utils import timezone
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

class TimeStampedModel(models.Model):
    """Abstract base model with timestamp fields"""
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        abstract = True


class AuditModel(TimeStampedModel):
    """Abstract model with audit fields"""
    
    created_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(class)s_created'
    )
    updated_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(class)s_updated'
    )
    
    class Meta:
        abstract = True


class SiteSettings(models.Model):
    """Global site settings"""
    
    # Company Information
    company_name = models.CharField(max_length=200, default='FlynJet')
    company_email = models.EmailField(default='info@flynjet.com')
    company_phone = models.CharField(max_length=20, default='+254785651832')
    whatsapp_number = models.CharField(max_length=20, default='+447393700477', verbose_name="WhatsApp Number")
    company_address = models.TextField(blank=True)
    
    # Social Media
    facebook_url = models.URLField(blank=True)
    twitter_url = models.URLField(blank=True)
    instagram_url = models.URLField(blank=True)
    linkedin_url = models.URLField(blank=True)
    youtube_url = models.URLField(blank=True)
    
    # SEO
    meta_title = models.CharField(max_length=200, default='FlynJet - Premium Private Jet Charter')
    meta_description = models.TextField(default='Experience luxury air travel with FlynJet. Private jet charters, cargo logistics, and premium aviation services.')
    meta_keywords = models.CharField(max_length=255, default='private jet, charter, cargo, aviation')
    
    # Analytics
    google_analytics_id = models.CharField(max_length=50, blank=True)
    facebook_pixel_id = models.CharField(max_length=50, blank=True)
    
    # Payment Settings
    stripe_public_key = models.CharField(max_length=255, blank=True)
    stripe_secret_key = models.CharField(max_length=255, blank=True)
    coinbase_api_key = models.CharField(max_length=255, blank=True)
    
    # Email Settings
    smtp_host = models.CharField(max_length=255, blank=True)
    smtp_port = models.IntegerField(default=587)
    smtp_username = models.CharField(max_length=255, blank=True)
    smtp_password = models.CharField(max_length=255, blank=True)
    
    # Booking Settings
    default_booking_expiry_hours = models.IntegerField(default=24)
    minimum_booking_hours = models.IntegerField(default=2)
    maximum_booking_months = models.IntegerField(default=12)
    
    # Currency Settings
    base_currency = models.CharField(max_length=3, default='USD')
    accepted_currencies = models.JSONField(default=list)
    
    # Feature Flags
    enable_crypto_payments = models.BooleanField(default=True)
    enable_social_login = models.BooleanField(default=True)
    enable_two_factor = models.BooleanField(default=True)
    enable_maintenance_mode = models.BooleanField(default=False)
    
    # Maintenance Mode
    maintenance_message = models.TextField(blank=True)
    maintenance_allowed_ips = models.JSONField(default=list)
    
    # Rate Limiting
    max_bookings_per_day = models.IntegerField(default=10)
    max_failed_logins = models.IntegerField(default=5)
    
    # Updated at
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name_plural = "Site Settings"
    
    def __str__(self):
        return "Site Settings"
    
    @classmethod
    def get_settings(cls):
        """Get or create site settings"""
        obj, created = cls.objects.get_or_create(pk=1)
        return obj


class Notification(models.Model):
    """System notifications"""
    
    NOTIFICATION_TYPES = (
        ('booking', 'Booking Update'),
        ('payment', 'Payment Update'),
        ('flight', 'Flight Status'),
        ('promotion', 'Promotion'),
        ('system', 'System Message'),
        ('security', 'Security Alert'),
        ('reminder', 'Reminder'),
        ('chat', 'Chat Message'),
    )
    
    NOTIFICATION_PRIORITIES = (
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Recipients
    recipient = models.ForeignKey('accounts.User', on_delete=models.CASCADE, related_name='notifications', null=True, blank=True)
    recipient_type = models.CharField(max_length=20, choices=(
        ('user', 'Specific User'),
        ('all', 'All Users'),
        ('admins', 'All Admins'),
        ('agents', 'All Agents'),
    ), default='user')
    
    # Notification Details
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    priority = models.CharField(max_length=10, choices=NOTIFICATION_PRIORITIES, default='medium')
    title = models.CharField(max_length=200)
    message = models.TextField()
    
    # Action
    action_url = models.URLField(blank=True)
    action_text = models.CharField(max_length=100, blank=True)
    
    # Related Object
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.CharField(max_length=100, null=True, blank=True)
    related_object = GenericForeignKey('content_type', 'object_id')
    
    # Status
    is_read = models.BooleanField(default=False)
    is_sent = models.BooleanField(default=False)
    is_archived = models.BooleanField(default=False)
    
    # Delivery
    email_sent = models.BooleanField(default=False)
    sms_sent = models.BooleanField(default=False)
    push_sent = models.BooleanField(default=False)
    
    # Schedule
    scheduled_for = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', '-created_at']),
            models.Index(fields=['notification_type', 'is_read']),
            models.Index(fields=['scheduled_for']),
        ]
    
    def __str__(self):
        return f"{self.get_notification_type_display()}: {self.title}"
    
    def mark_as_read(self):
        """Mark notification as read"""
        self.is_read = True
        self.save(update_fields=['is_read'])
    
    def mark_as_sent(self):
        """Mark notification as sent"""
        self.is_sent = True
        self.sent_at = timezone.now()
        self.save(update_fields=['is_sent', 'sent_at'])


class SupportTicket(models.Model):
    """Customer support tickets"""
    
    TICKET_STATUS = (
        ('new', 'New'),
        ('open', 'Open'),
        ('in_progress', 'In Progress'),
        ('waiting', 'Waiting for Customer'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
        ('escalated', 'Escalated'),
    )
    
    TICKET_PRIORITIES = (
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    )
    
    TICKET_CATEGORIES = (
        ('booking', 'Booking Issue'),
        ('payment', 'Payment Issue'),
        ('technical', 'Technical Support'),
        ('billing', 'Billing Question'),
        ('flight', 'Flight Information'),
        ('cancellation', 'Cancellation'),
        ('refund', 'Refund Request'),
        ('feedback', 'Feedback'),
        ('other', 'Other'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ticket_number = models.CharField(max_length=50, unique=True)
    
    # User
    user = models.ForeignKey('accounts.User', on_delete=models.PROTECT, related_name='support_tickets')
    
    # Ticket Details
    category = models.CharField(max_length=20, choices=TICKET_CATEGORIES)
    status = models.CharField(max_length=20, choices=TICKET_STATUS, default='new')
    priority = models.CharField(max_length=10, choices=TICKET_PRIORITIES, default='medium')
    subject = models.CharField(max_length=200)
    description = models.TextField()
    
    # Related Booking
    booking = models.ForeignKey('bookings.Booking', on_delete=models.SET_NULL, null=True, blank=True)
    
    # Attachments
    attachments = models.FileField(upload_to='support_attachments/', blank=True)
    
    # Assignment
    assigned_to = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_tickets')
    assigned_at = models.DateTimeField(null=True, blank=True)
    
    # Resolution
    resolution = models.TextField(blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='resolved_tickets')
    
    # Customer Rating
    rating = models.IntegerField(null=True, blank=True, choices=[(i, i) for i in range(1, 6)])
    feedback = models.TextField(blank=True)
    
    # Metadata
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['ticket_number']),
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['status', 'priority']),
            models.Index(fields=['assigned_to', 'status']),
        ]
    
    def __str__(self):
        return f"Ticket {self.ticket_number}: {self.subject}"
    
    def save(self, *args, **kwargs):
        if not self.ticket_number:
            self.ticket_number = self.generate_ticket_number()
        super().save(*args, **kwargs)
    
    def generate_ticket_number(self):
        """Generate unique ticket number"""
        import random
        import string
        timestamp = timezone.now().strftime('%Y%m')
        random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        return f"TKT{timestamp}{random_str}"
    
    def assign_to(self, agent):
        """Assign ticket to agent"""
        self.assigned_to = agent
        self.assigned_at = timezone.now()
        self.status = 'open'
        self.save(update_fields=['assigned_to', 'assigned_at', 'status'])
        
        # Create notification
        Notification.objects.create(
            recipient=agent,
            notification_type='system',
            title='New Ticket Assignment',
            message=f"Ticket {self.ticket_number} has been assigned to you",
            action_url=f"/admin/support/ticket/{self.id}/",
            related_object=self
        )
    
    def resolve(self, resolution, user):
        """Resolve ticket"""
        self.status = 'resolved'
        self.resolution = resolution
        self.resolved_at = timezone.now()
        self.resolved_by = user
        self.save(update_fields=['status', 'resolution', 'resolved_at', 'resolved_by'])
        
        # Notify customer
        Notification.objects.create(
            recipient=self.user,
            notification_type='system',
            title='Ticket Resolved',
            message=f"Your ticket '{self.subject}' has been resolved",
            action_url=f"/support/ticket/{self.ticket_number}/",
            related_object=self
        )


class SupportMessage(models.Model):
    """Messages within support tickets"""
    
    ticket = models.ForeignKey(SupportTicket, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey('accounts.User', on_delete=models.PROTECT)
    message = models.TextField()
    
    # Attachments
    attachment = models.FileField(upload_to='support_messages/', blank=True)
    
    # Read Status
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    
    # Internal Note (not visible to customer)
    is_internal = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['created_at']
    
    def __str__(self):
        return f"Message from {self.sender.email} on {self.created_at}"
    
    def mark_as_read(self):
        """Mark message as read"""
        self.is_read = True
        self.read_at = timezone.now()
        self.save(update_fields=['is_read', 'read_at'])


class FAQ(models.Model):
    """Frequently Asked Questions"""
    
    FAQ_CATEGORIES = (
        ('booking', 'Booking'),
        ('payment', 'Payment'),
        ('flight', 'Flight Information'),
        ('cancellation', 'Cancellation & Refunds'),
        ('safety', 'Safety'),
        ('baggage', 'Baggage'),
        ('membership', 'Membership'),
        ('general', 'General'),
    )
    
    question = models.CharField(max_length=500)
    answer = models.TextField()
    category = models.CharField(max_length=20, choices=FAQ_CATEGORIES, default='general')
    sort_order = models.IntegerField(default=0)
    is_published = models.BooleanField(default=True)
    
    # SEO
    meta_title = models.CharField(max_length=200, blank=True)
    meta_description = models.TextField(blank=True)
    
    # Statistics
    views_count = models.IntegerField(default=0)
    helpful_count = models.IntegerField(default=0)
    not_helpful_count = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['category', 'sort_order']
        verbose_name = "FAQ"
        verbose_name_plural = "FAQs"
    
    def __str__(self):
        return self.question
    
    def increment_views(self):
        """Increment view count"""
        self.views_count += 1
        self.save(update_fields=['views_count'])
    
    def mark_helpful(self):
        """Mark FAQ as helpful"""
        self.helpful_count += 1
        self.save(update_fields=['helpful_count'])
    
    def mark_not_helpful(self):
        """Mark FAQ as not helpful"""
        self.not_helpful_count += 1
        self.save(update_fields=['not_helpful_count'])


class Testimonial(models.Model):
    """Customer testimonials"""
    
    user = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='core_testimonials')
    customer_name = models.CharField(max_length=200)
    customer_title = models.CharField(max_length=200, blank=True)
    customer_company = models.CharField(max_length=200, blank=True)
    customer_image = models.ImageField(upload_to='testimonials/', blank=True)
    
    # Testimonial Content
    content = models.TextField()
    rating = models.IntegerField(choices=[(i, i) for i in range(1, 6)])
    
    # Related Booking
    booking = models.ForeignKey('bookings.Booking', on_delete=models.SET_NULL, null=True, blank=True)
    
    # Status
    is_featured = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    is_published = models.BooleanField(default=True)
    
    # Verification
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='verified_core_testimonials')
    
    # Metadata
    sort_order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-is_featured', 'sort_order', '-created_at']
    
    def __str__(self):
        return f"Testimonial by {self.customer_name}"
    
    def verify(self, user):
        """Verify testimonial"""
        self.is_verified = True
        self.verified_at = timezone.now()
        self.verified_by = user
        self.save(update_fields=['is_verified', 'verified_at', 'verified_by'])

class ActivityLog(models.Model):
    """Track all system activities"""
    
    ACTIVITY_TYPES = (
        ('user_login', 'User Login'),
        ('user_logout', 'User Logout'),
        ('booking_created', 'Booking Created'),
        ('booking_updated', 'Booking Updated'),
        ('booking_cancelled', 'Booking Cancelled'),
        ('payment_made', 'Payment Made'),
        ('payment_failed', 'Payment Failed'),
        ('refund_processed', 'Refund Processed'),
        ('ticket_created', 'Support Ticket Created'),
        ('ticket_resolved', 'Support Ticket Resolved'),
        ('user_registered', 'User Registered'),
        ('password_change', 'Password Changed'),
        ('profile_updated', 'Profile Updated'),
        ('admin_action', 'Admin Action'),
    )
    
    user = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True)
    activity_type = models.CharField(max_length=50, choices=ACTIVITY_TYPES)
    description = models.TextField()
    
    # Related Object
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True)
    object_id = models.CharField(max_length=100)
    related_object = GenericForeignKey('content_type', 'object_id')
    
    # Metadata
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    data = models.JSONField(default=dict, blank=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', '-timestamp']),
            models.Index(fields=['activity_type', '-timestamp']),
            models.Index(fields=['timestamp']),
        ]
    
    def __str__(self):
        return f"{self.activity_type} by {self.user} at {self.timestamp}"

class NewsletterSubscriber(models.Model):
    """Newsletter subscribers"""
    email = models.EmailField(unique=True)
    is_active = models.BooleanField(default=True)
    subscribed_at = models.DateTimeField(auto_now_add=True)
    unsubscribed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-subscribed_at']
    
    def __str__(self):
        return self.email
    
    def unsubscribe(self):
        self.is_active = False
        self.unsubscribed_at = timezone.now()
        self.save()

# apps/core/models.py - Update the AdminNotification class

class AdminNotification(models.Model):
    """Admin notifications for new enquiries, payments, etc."""
    
    NOTIFICATION_TYPES = (
        ('enquiry', 'New Enquiry'),
        ('payment', 'New Payment'),
        ('booking', 'New Booking'),
        ('contract', 'Contract Update'),
        ('system', 'System Alert'),
        ('dispute', 'New Dispute'),
        ('support', 'New Support Ticket'),
        ('review', 'New Review'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=200)
    message = models.TextField()
    link = models.CharField(max_length=500, blank=True, help_text="URL to navigate when clicked")
    
    # Optional: track source object for future reference
    source_model = models.CharField(max_length=100, blank=True)
    source_id = models.CharField(max_length=100, blank=True)
    
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['is_read', 'created_at']),
            models.Index(fields=['notification_type']),
        ]
    
    def __str__(self):
        return f"{self.get_notification_type_display()}: {self.title}"
    
    def mark_as_read(self):
        self.is_read = True
        self.save(update_fields=['is_read'])
        
class BankDetail(models.Model):
    """Bank account details - editable by admin (no JSON)"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    bank_name = models.CharField(max_length=200)
    account_name = models.CharField(max_length=200)
    account_number = models.CharField(max_length=50)
    routing_number = models.CharField(max_length=50, blank=True, help_text="Routing/ABA number")
    swift_code = models.CharField(max_length=20, blank=True, help_text="SWIFT/BIC code")
    iban = models.CharField(max_length=50, blank=True)
    currency = models.CharField(max_length=3, default='USD')
    country = models.CharField(max_length=100, blank=True)
    branch_address = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    sort_order = models.IntegerField(default=0)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['sort_order']
        verbose_name = "Bank Detail"
        verbose_name_plural = "Bank Details"
    
    def __str__(self):
        return f"{self.bank_name} - {self.account_number}"
    
    def save(self, *args, **kwargs):
        if self.is_default:
            BankDetail.objects.filter(is_default=True).update(is_default=False)
        super().save(*args, **kwargs)


class CryptoWallet(models.Model):
    """Cryptocurrency wallet details - editable by admin (no JSON)"""
    
    NETWORK_CHOICES = (
        ('erc20', 'ERC-20 (Ethereum)'),
        ('trc20', 'TRC-20 (Tron)'),
        ('bep20', 'BEP-20 (Binance Smart Chain)'),
        ('solana', 'Solana'),
        ('bitcoin', 'Bitcoin (Native)'),
        ('lightning', 'Lightning Network'),
    )
    
    CRYPTO_CHOICES = (
        ('usdt', 'USDT'),
        ('usdc', 'USDC'),
        ('btc', 'Bitcoin'),
        ('eth', 'Ethereum'),
        ('sol', 'Solana'),
        ('bnb', 'BNB'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    crypto_type = models.CharField(max_length=20, choices=CRYPTO_CHOICES)
    network = models.CharField(max_length=20, choices=NETWORK_CHOICES)
    wallet_address = models.CharField(max_length=200)
    wallet_name = models.CharField(max_length=100, blank=True, help_text="Label for this wallet")
    qr_code = models.ImageField(upload_to='crypto_qr/', blank=True, null=True)
    
    # NEW FIELD - Optional link URL
    link_url = models.URLField(max_length=500, blank=True, help_text="Optional link (e.g., blockchain explorer, exchange link)")
    link_text = models.CharField(max_length=100, blank=True, help_text="Link text (e.g., 'View on Explorer', 'Buy USDT')")
    
    min_deposit = models.DecimalField(max_digits=20, decimal_places=8, default=0)
    max_deposit = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    sort_order = models.IntegerField(default=0)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['sort_order']
        unique_together = ['crypto_type', 'network']
        verbose_name = "Crypto Wallet"
        verbose_name_plural = "Crypto Wallets"
    
    def __str__(self):
        return f"{self.get_crypto_type_display()} ({self.get_network_display()}): {self.wallet_address[:20]}..."
    
    def get_link_display(self):
        """Get link text or default"""
        if self.link_text:
            return self.link_text
        if self.link_url:
            return "View Details"
        return ""
    
    def save(self, *args, **kwargs):
        if self.is_default:
            CryptoWallet.objects.filter(is_default=True, crypto_type=self.crypto_type).update(is_default=False)
        super().save(*args, **kwargs)


class OfficeLocation(models.Model):
    """Office locations for footer - editable by admin (no JSON)"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    city = models.CharField(max_length=100)
    country = models.CharField(max_length=100)
    address = models.TextField()
    phone = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    latitude = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_headquarters = models.BooleanField(default=False)
    sort_order = models.IntegerField(default=0)
    working_hours = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['sort_order']
        verbose_name = "Office Location"
        verbose_name_plural = "Office Locations"
    
    def __str__(self):
        return f"{self.city}, {self.country}"
    
    def save(self, *args, **kwargs):
        if self.is_headquarters:
            OfficeLocation.objects.filter(is_headquarters=True).update(is_headquarters=False)
        super().save(*args, **kwargs)


class CompanyContact(models.Model):
    """Company contact numbers - editable by admin (no JSON)"""
    
    CONTACT_CHOICES = (
        ('phone', 'Phone Number'),
        ('whatsapp', 'WhatsApp Number'),
        ('email', 'Email Address'),
        ('emergency', 'Emergency Contact'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    contact_type = models.CharField(max_length=20, choices=CONTACT_CHOICES)
    value = models.CharField(max_length=255)
    label = models.CharField(max_length=100, blank=True, help_text="e.g., 'Sales', 'Support'")
    is_active = models.BooleanField(default=True)
    is_primary = models.BooleanField(default=False)
    sort_order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['contact_type', 'sort_order']
        verbose_name = "Company Contact"
        verbose_name_plural = "Company Contacts"
    
    def __str__(self):
        return f"{self.get_contact_type_display()}: {self.value}"
    
    def save(self, *args, **kwargs):
        if self.is_primary:
            CompanyContact.objects.filter(contact_type=self.contact_type, is_primary=True).update(is_primary=False)
        super().save(*args, **kwargs)


class PaymentMethodConfig(models.Model):
    """Payment method configuration - toggle on/off, maintenance mode (no JSON)"""
    
    METHOD_CHOICES = (
        ('paystack', 'Paystack (Cards)'),
        ('bank_transfer', 'Bank Transfer'),
        ('wire_transfer', 'Wire Transfer'),
        ('crypto_all', 'Cryptocurrency (All)'),
        ('usdt_erc20', 'USDT (ERC-20)'),
        ('usdt_trc20', 'USDT (TRC-20)'),
        ('bitcoin', 'Bitcoin'),
        ('ethereum', 'Ethereum'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    method_key = models.CharField(max_length=50, choices=METHOD_CHOICES, unique=True)
    display_name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    icon_class = models.CharField(max_length=50, default='fas fa-credit-card')
    
    # Toggle settings
    is_enabled = models.BooleanField(default=True, help_text="Enable this payment method")
    is_visible = models.BooleanField(default=True, help_text="Show on checkout page")
    is_maintenance = models.BooleanField(default=False, help_text="Under maintenance mode")
    
    # Maintenance message
    maintenance_message = models.CharField(
        max_length=200, 
        blank=True, 
        default="This payment method is currently under maintenance. Please use another payment method."
    )
    
    # Ordering
    sort_order = models.IntegerField(default=0)
    
    # Fees (percentage)
    fee_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    fee_fixed = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Limits
    min_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    max_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['sort_order']
        verbose_name = "Payment Method Config"
        verbose_name_plural = "Payment Method Configs"
    
    def __str__(self):
        status = "✓" if self.is_enabled else "✗"
        maint = " 🔧" if self.is_maintenance else ""
        return f"[{status}] {self.display_name}{maint}"
    
    def get_status_display(self):
        if not self.is_enabled:
            return "Disabled"
        if self.is_maintenance:
            return "Maintenance"
        return "Active"

# apps/core/models.py - Add this at the end

class SocialLink(models.Model):
    """Dynamic social media links - admin can add/remove any platform"""
    
    SOCIAL_PLATFORMS = (
        ('facebook', 'Facebook'),
        ('twitter', 'Twitter / X'),
        ('instagram', 'Instagram'),
        ('linkedin', 'LinkedIn'),
        ('youtube', 'YouTube'),
        ('tiktok', 'TikTok'),
        ('whatsapp', 'WhatsApp'),
        ('telegram', 'Telegram'),
        ('snapchat', 'Snapchat'),
        ('pinterest', 'Pinterest'),
        ('github', 'GitHub'),
        ('reddit', 'Reddit'),
        ('tumblr', 'Tumblr'),
        ('wechat', 'WeChat'),
        ('line', 'Line'),
        ('discord', 'Discord'),
        ('twitch', 'Twitch'),
        ('medium', 'Medium'),
        ('patreon', 'Patreon'),
        ('custom', 'Custom Platform'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    platform = models.CharField(max_length=50, choices=SOCIAL_PLATFORMS)
    url = models.URLField(max_length=500, help_text="Full URL to your profile/page")
    icon_class = models.CharField(max_length=100, blank=True, help_text="Font Awesome icon class (e.g., 'fab fa-facebook')")
    custom_name = models.CharField(max_length=100, blank=True, help_text="Custom name if platform is 'custom'")
    
    # Display settings
    is_active = models.BooleanField(default=True)
    open_in_new_tab = models.BooleanField(default=True)
    sort_order = models.IntegerField(default=0)
    
    # Optional tracking
    utm_source = models.CharField(max_length=100, blank=True)
    utm_medium = models.CharField(max_length=100, blank=True)
    utm_campaign = models.CharField(max_length=100, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['sort_order']
        verbose_name = "Social Link"
        verbose_name_plural = "Social Links"
    
    def __str__(self):
        return f"{self.get_platform_display()}: {self.url}"
    
    def get_icon_class(self):
        """Get the appropriate icon class for the platform"""
        if self.icon_class:
            return self.icon_class
        
        default_icons = {
            'facebook': 'fab fa-facebook-f',
            'twitter': 'fab fa-twitter',
            'instagram': 'fab fa-instagram',
            'linkedin': 'fab fa-linkedin-in',
            'youtube': 'fab fa-youtube',
            'tiktok': 'fab fa-tiktok',
            'whatsapp': 'fab fa-whatsapp',
            'telegram': 'fab fa-telegram-plane',
            'snapchat': 'fab fa-snapchat-ghost',
            'pinterest': 'fab fa-pinterest-p',
            'github': 'fab fa-github',
            'reddit': 'fab fa-reddit-alien',
            'tumblr': 'fab fa-tumblr',
            'wechat': 'fab fa-weixin',
            'line': 'fab fa-line',
            'discord': 'fab fa-discord',
            'twitch': 'fab fa-twitch',
            'medium': 'fab fa-medium-m',
            'patreon': 'fab fa-patreon',
            'custom': 'fas fa-link',
        }
        return default_icons.get(self.platform, 'fas fa-link')
    
    def get_display_name(self):
        """Get display name for the platform"""
        if self.platform == 'custom' and self.custom_name:
            return self.custom_name
        return self.get_platform_display()
    
    def get_full_url_with_tracking(self):
        """Get URL with UTM parameters appended"""
        if not (self.utm_source or self.utm_medium or self.utm_campaign):
            return self.url
        
        from urllib.parse import urlparse, urlunparse, parse_qs, urlencode
        
        parsed = urlparse(self.url)
        query_params = parse_qs(parsed.query)
        
        if self.utm_source:
            query_params['utm_source'] = [self.utm_source]
        if self.utm_medium:
            query_params['utm_medium'] = [self.utm_medium]
        if self.utm_campaign:
            query_params['utm_campaign'] = [self.utm_campaign]
        
        new_query = urlencode(query_params, doseq=True)
        return urlunparse(parsed._replace(query=new_query))
    
    def save(self, *args, **kwargs):
        if not self.icon_class:
            self.icon_class = self.get_icon_class()
        super().save(*args, **kwargs)