import uuid
import pyotp
import qrcode
import io
import base64
from datetime import timedelta
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.utils import timezone
from django.core.mail import send_mail
from django.core.validators import RegexValidator, MinLengthValidator
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.validators import UnicodeUsernameValidator
from phonenumber_field.modelfields import PhoneNumberField
from imagekit.models import ProcessedImageField
from imagekit.processors import ResizeToFill
from apps.core.models import TimeStampedModel, AuditModel
import logging

logger = logging.getLogger(__name__)

class UserManager(BaseUserManager):
    """Custom user manager for FlynJet users."""
    
    def create_user(self, email, password=None, **extra_fields):
        """Create and save a regular user."""
        if not email:
            raise ValueError(_('The Email must be set'))
        email = self.normalize_email(email)
        
        # Generate username from email if not provided
        if 'username' not in extra_fields:
            extra_fields['username'] = email.split('@')[0]
        
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        
        # Use get_or_create for all related models to prevent duplicates
        UserProfile.objects.get_or_create(user=user)
        UserSecuritySettings.objects.get_or_create(user=user)
        UserNotificationPreferences.objects.get_or_create(user=user)
        
        logger.info(f"New user created: {email}")
        return user
            
    def create_superuser(self, email, password, **extra_fields):
        """Create and save a superuser."""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('user_type', 'admin')
        extra_fields.setdefault('email_verified', True)
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError(_('Superuser must have is_staff=True.'))
        if extra_fields.get('is_superuser') is not True:
            raise ValueError(_('Superuser must have is_superuser=True.'))
        
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """Custom User model for FlynJet."""
    
    USER_TYPES = (
        ('user', 'Regular User'),
        ('agent', 'Agent'),
        ('admin', 'Administrator'),
        ('maintenance', 'Maintenance Team'),
        ('pilot', 'Pilot'),
        ('crew', 'Crew Member'),
        ('corporate', 'Corporate Client'),
    )
    
    DOCUMENT_TYPES = (
        ('passport', 'Passport'),
        ('driving_license', 'Driving License'),
        ('national_id', 'National ID'),
        ('company_reg', 'Company Registration'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = models.CharField(
        _('username'),
        max_length=150,
        unique=True,
        help_text=_('Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.'),
        validators=[UnicodeUsernameValidator()],
        error_messages={
            'unique': _("A user with that username already exists."),
        },
    )
    email = models.EmailField(_('email address'), unique=True, db_index=True)
    
    # Personal Information
    first_name = models.CharField(_('first name'), max_length=150, blank=True)
    last_name = models.CharField(_('last name'), max_length=150, blank=True)
    user_type = models.CharField(max_length=20, choices=USER_TYPES, default='user')
    phone_number = PhoneNumberField(_('phone number'), blank=True, null=True, region='US')
    alternate_phone = PhoneNumberField(blank=True, null=True, region='US')
    date_of_birth = models.DateField(_('date of birth'), null=True, blank=True)
    
    # Address
    address_line1 = models.CharField(max_length=255, blank=True)
    address_line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    
    # Company Information (for corporate clients)
    company_name = models.CharField(max_length=255, blank=True)
    company_registration_number = models.CharField(max_length=100, blank=True)
    company_vat_number = models.CharField(max_length=100, blank=True)
    company_website = models.URLField(blank=True)
    
    # Verification Status
    email_verified = models.BooleanField(default=False)
    phone_verified = models.BooleanField(default=False)
    identity_verified = models.BooleanField(default=False)
    verified_at = models.DateTimeField(null=True, blank=True)
    
    # Document Verification
    id_document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPES, blank=True)
    id_document_number = models.CharField(max_length=100, blank=True)
    id_document_front = models.ImageField(upload_to='id_documents/', blank=True, null=True)
    id_document_back = models.ImageField(upload_to='id_documents/', blank=True, null=True)
    id_verification_status = models.CharField(
        max_length=20,
        choices=(
            ('pending', 'Pending'),
            ('verified', 'Verified'),
            ('rejected', 'Rejected'),
        ),
        default='pending'
    )
    
    # Preferences
    preferred_language = models.CharField(
        max_length=10,
        choices=(
            ('en', 'English'),
            ('es', 'Spanish'),
            ('fr', 'French'),
            ('ar', 'Arabic'),
            ('zh', 'Chinese'),
        ),
        default='en'
    )
    preferred_currency = models.CharField(
        max_length=3,
        choices=(
            ('USD', 'US Dollar'),
            ('EUR', 'Euro'),
            ('GBP', 'British Pound'),
            ('AED', 'UAE Dirham'),
        ),
        default='USD'
    )
    marketing_consent = models.BooleanField(default=False)
    data_processing_consent = models.BooleanField(default=False)
    consent_given_at = models.DateTimeField(null=True, blank=True)
    
    # Security
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)
    last_login_user_agent = models.TextField(blank=True)
    failed_login_attempts = models.IntegerField(default=0)
    last_failed_login = models.DateTimeField(null=True, blank=True)
    account_locked_until = models.DateTimeField(null=True, blank=True)
    password_changed_at = models.DateTimeField(auto_now_add=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_suspended = models.BooleanField(default=False)
    suspension_reason = models.TextField(blank=True)
    suspended_at = models.DateTimeField(null=True, blank=True)
    suspended_until = models.DateTimeField(null=True, blank=True)
    deactivated_at = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    date_joined = models.DateTimeField(_('date joined'), default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    last_activity = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True)
    
    objects = UserManager()
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']
    
    class Meta:
        verbose_name = _('user')
        verbose_name_plural = _('users')
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['user_type']),
            models.Index(fields=['is_active']),
            models.Index(fields=['date_joined']),
            models.Index(fields=['id_verification_status']),
        ]
    
    def __str__(self):
        return f"{self.get_full_name()} ({self.email})"
    
    def get_full_name(self):
        """Return the full name of the user."""
        return f"{self.first_name} {self.last_name}".strip() or self.email
    
    def get_short_name(self):
        """Return the short name of the user."""
        return self.first_name or self.email.split('@')[0]
    
    def email_user(self, subject, message, from_email=None, **kwargs):
        """Send an email to this user."""
        send_mail(subject, message, from_email, [self.email], **kwargs)
    
    def record_login(self, request):
        """Record login details."""
        self.last_login = timezone.now()
        self.last_login_ip = self.get_client_ip(request)
        self.last_login_user_agent = request.META.get('HTTP_USER_AGENT', '')
        self.failed_login_attempts = 0
        self.last_activity = timezone.now()
        self.save(update_fields=['last_login', 'last_login_ip', 'last_login_user_agent', 
                                 'failed_login_attempts', 'last_activity'])
        
        # Create login history
        LoginHistory.objects.create(
            user=self,
            ip_address=self.last_login_ip,
            user_agent=self.last_login_user_agent,
            login_type='login'
        )
    
    def record_failed_login(self):
        """Record failed login attempt."""
        self.failed_login_attempts += 1
        self.last_failed_login = timezone.now()
        
        # Lock account after 5 failed attempts
        if self.failed_login_attempts >= 5:
            self.account_locked_until = timezone.now() + timedelta(minutes=30)
        
        self.save(update_fields=['failed_login_attempts', 'last_failed_login', 'account_locked_until'])
    
    def is_account_locked(self):
        """Check if account is locked."""
        if self.account_locked_until and self.account_locked_until > timezone.now():
            return True
        return False
    
    def get_client_ip(self, request):
        """Get client IP from request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def verify_email(self):
        """Mark email as verified."""
        self.email_verified = True
        self.verified_at = timezone.now()
        self.save(update_fields=['email_verified', 'verified_at'])
    
    def verify_phone(self):
        """Mark phone as verified."""
        self.phone_verified = True
        self.save(update_fields=['phone_verified'])
    
    def suspend_account(self, reason, until=None):
        """Suspend user account."""
        self.is_suspended = True
        self.suspension_reason = reason
        self.suspended_at = timezone.now()
        self.suspended_until = until
        self.is_active = False
        self.save(update_fields=['is_suspended', 'suspension_reason', 'suspended_at', 
                                'suspended_until', 'is_active'])
        
        # Notify user
        self.email_user(
            'Account Suspended',
            f'Your account has been suspended. Reason: {reason}'
        )
    
    def reactivate_account(self):
        """Reactivate suspended account."""
        self.is_suspended = False
        self.suspension_reason = ''
        self.suspended_at = None
        self.suspended_until = None
        self.is_active = True
        self.save(update_fields=['is_suspended', 'suspension_reason', 'suspended_at',
                                'suspended_until', 'is_active'])


class UserProfile(models.Model):
    """Extended user profile information."""
    
    GENDER_CHOICES = (
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other'),
        ('N', 'Prefer not to say'),
    )
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    
    # Profile Image
    profile_image = ProcessedImageField(
        upload_to='profile_pics/',
        processors=[ResizeToFill(300, 300)],
        format='JPEG',
        options={'quality': 90},
        null=True,
        blank=True
    )
    
    # Personal Details
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, blank=True)
    nationality = models.CharField(max_length=100, blank=True)
    passport_number = models.CharField(max_length=50, blank=True)
    passport_expiry = models.DateField(null=True, blank=True)
    frequent_flyer_number = models.CharField(max_length=50, blank=True)
    preferred_airport = models.CharField(max_length=3, blank=True)  # IATA code
    
    # Emergency Contact
    emergency_contact_name = models.CharField(max_length=200, blank=True)
    emergency_contact_phone = PhoneNumberField(blank=True, null=True, region='US')
    emergency_contact_relation = models.CharField(max_length=100, blank=True)
    
    # Special Requirements
    dietary_restrictions = models.TextField(blank=True)
    medical_conditions = models.TextField(blank=True)
    special_assistance_required = models.BooleanField(default=False)
    
    # Travel Preferences
    seat_preference = models.CharField(
        max_length=20,
        choices=(
            ('window', 'Window'),
            ('aisle', 'Aisle'),
            ('middle', 'Middle'),
        ),
        blank=True
    )
    meal_preference = models.CharField(
        max_length=50,
        choices=(
            ('regular', 'Regular'),
            ('vegetarian', 'Vegetarian'),
            ('vegan', 'Vegan'),
            ('halal', 'Halal'),
            ('kosher', 'Kosher'),
            ('gluten_free', 'Gluten Free'),
        ),
        blank=True
    )
    
    # Corporate Details (if corporate client)
    corporate_title = models.CharField(max_length=100, blank=True)
    corporate_department = models.CharField(max_length=100, blank=True)
    corporate_cost_center = models.CharField(max_length=100, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'User Profile'
        verbose_name_plural = 'User Profiles'
    
    def __str__(self):
        return f"Profile for {self.user.get_full_name()}"
    
    @property
    def profile_image_url(self):
        """Get profile image URL or default."""
        if self.profile_image:
            return self.profile_image.url
        return '/static/images/default-profile.png'


class LoginHistory(models.Model):
    """Track user login history."""
    
    LOGIN_TYPES = (
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('failed', 'Failed Attempt'),
        ('password_change', 'Password Change'),
        ('2fa_attempt', '2FA Attempt'),
        ('social_login', 'Social Login'),
    )
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='login_history')
    login_type = models.CharField(max_length=20, choices=LOGIN_TYPES)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    location = models.CharField(max_length=255, blank=True)
    device_type = models.CharField(max_length=50, blank=True)
    browser = models.CharField(max_length=100, blank=True)
    operating_system = models.CharField(max_length=100, blank=True)
    success = models.BooleanField(default=True)
    failure_reason = models.CharField(max_length=255, blank=True)
    session_key = models.CharField(max_length=40, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        verbose_name = 'Login History'
        verbose_name_plural = 'Login Histories'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['login_type', 'timestamp']),
            models.Index(fields=['ip_address']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.login_type} at {self.timestamp}"


class UserSecuritySettings(models.Model):
    """User security preferences and settings."""
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='security_settings')
    
    # Two Factor Authentication
    two_factor_enabled = models.BooleanField(default=False)
    two_factor_secret = models.CharField(max_length=32, blank=True)
    two_factor_backup_codes = models.JSONField(default=list, blank=True)
    two_factor_last_used = models.DateTimeField(null=True, blank=True)
    
    # Session Management
    session_timeout = models.IntegerField(default=30)  # minutes
    max_concurrent_sessions = models.IntegerField(default=5)
    remember_device_days = models.IntegerField(default=30)
    
    # Login Alerts
    alert_on_new_device = models.BooleanField(default=True)
    alert_on_new_location = models.BooleanField(default=True)
    alert_on_failed_login = models.BooleanField(default=True)
    alert_email = models.EmailField(blank=True)
    alert_sms = models.BooleanField(default=False)
    
    # Password Policy
    password_last_changed = models.DateTimeField(auto_now_add=True)
    password_expiry_days = models.IntegerField(default=90)
    password_history = models.JSONField(default=list)  # Store last 5 passwords
    
    # API Security
    api_key = models.CharField(max_length=64, blank=True)
    api_key_created = models.DateTimeField(null=True, blank=True)
    api_key_last_used = models.DateTimeField(null=True, blank=True)
    api_rate_limit = models.IntegerField(default=1000)  # requests per hour
    
    # Trusted Devices
    trusted_devices = models.JSONField(default=list)  # List of device fingerprints
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'User Security Settings'
        verbose_name_plural = 'User Security Settings'
    
    def generate_2fa_secret(self):
        """Generate new 2FA secret."""
        self.two_factor_secret = pyotp.random_base32()
        self.save(update_fields=['two_factor_secret'])
        return self.two_factor_secret
    
    def get_2fa_provisioning_uri(self, issuer_name="FlynJet"):
        """Get provisioning URI for QR code."""
        if not self.two_factor_secret:
            self.generate_2fa_secret()
        
        totp = pyotp.TOTP(self.two_factor_secret)
        return totp.provisioning_uri(
            name=self.user.email,
            issuer_name=issuer_name
        )
    
    def generate_2fa_qr_code(self):
        """Generate QR code for 2FA setup."""
        uri = self.get_2fa_provisioning_uri()
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(uri)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Convert to base64 for HTML display
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        image_base64 = base64.b64encode(buffer.getvalue()).decode()
        
        return f"data:image/png;base64,{image_base64}"
    
    def verify_2fa_code(self, code):
        """Verify 2FA code."""
        if not self.two_factor_secret:
            return False
        
        totp = pyotp.TOTP(self.two_factor_secret)
        valid = totp.verify(code, valid_window=1)
        
        if valid:
            self.two_factor_last_used = timezone.now()
            self.save(update_fields=['two_factor_last_used'])
        
        return valid
    
    def generate_backup_codes(self, count=10):
        """Generate backup codes for 2FA."""
        import secrets
        codes = []
        for _ in range(count):
            code = secrets.token_hex(5).upper()
            codes.append(code)
        
        self.two_factor_backup_codes = codes
        self.save(update_fields=['two_factor_backup_codes'])
        return codes
    
    def verify_backup_code(self, code):
        """Verify and consume a backup code."""
        if code in self.two_factor_backup_codes:
            self.two_factor_backup_codes.remove(code)
            self.save(update_fields=['two_factor_backup_codes'])
            return True
        return False
    
    def generate_api_key(self):
        """Generate new API key."""
        import secrets
        self.api_key = secrets.token_urlsafe(48)
        self.api_key_created = timezone.now()
        self.save(update_fields=['api_key', 'api_key_created'])
        return self.api_key
    
    def add_to_password_history(self, password_hash):
        """Add password hash to history."""
        history = self.password_history
        history.append(password_hash)
        
        # Keep only last 5
        if len(history) > 5:
            history = history[-5:]
        
        self.password_history = history
        self.save(update_fields=['password_history'])


class UserNotificationPreferences(models.Model):
    """User notification preferences."""
    
    NOTIFICATION_CHANNELS = (
        ('email', 'Email'),
        ('sms', 'SMS'),
        ('push', 'Push Notification'),
        ('whatsapp', 'WhatsApp'),
        ('telegram', 'Telegram'),
    )
    
    NOTIFICATION_TYPES = (
        ('booking', 'Booking Updates'),
        ('payment', 'Payment Notifications'),
        ('flight', 'Flight Status'),
        ('promotion', 'Promotions & Offers'),
        ('security', 'Security Alerts'),
        ('system', 'System Updates'),
        ('newsletter', 'Newsletter'),
    )
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='notification_preferences')
    
    # Channel preferences
    email_notifications = models.BooleanField(default=True)
    sms_notifications = models.BooleanField(default=False)
    push_notifications = models.BooleanField(default=True)
    whatsapp_notifications = models.BooleanField(default=False)
    telegram_notifications = models.BooleanField(default=False)
    
    # Telegram details
    telegram_chat_id = models.CharField(max_length=100, blank=True)
    
    # WhatsApp details
    whatsapp_number = PhoneNumberField(blank=True, null=True, region='US')
    
    # Notification type preferences
    booking_updates = models.BooleanField(default=True)
    payment_notifications = models.BooleanField(default=True)
    flight_status = models.BooleanField(default=True)
    promotions = models.BooleanField(default=False)
    security_alerts = models.BooleanField(default=True)
    system_updates = models.BooleanField(default=True)
    newsletter = models.BooleanField(default=False)
    
    # Quiet hours
    quiet_hours_enabled = models.BooleanField(default=False)
    quiet_hours_start = models.TimeField(null=True, blank=True)
    quiet_hours_end = models.TimeField(null=True, blank=True)
    quiet_hours_timezone = models.CharField(max_length=50, default='UTC')
    
    # Frequency
    digest_frequency = models.CharField(
        max_length=20,
        choices=(
            ('instant', 'Instant'),
            ('hourly', 'Hourly'),
            ('daily', 'Daily'),
            ('weekly', 'Weekly'),
        ),
        default='instant'
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'User Notification Preferences'
        verbose_name_plural = 'User Notification Preferences'
    
    def __str__(self):
        return f"Notification preferences for {self.user.email}"
    
    def get_preferred_channels(self):
        """Get list of preferred notification channels."""
        channels = []
        if self.email_notifications:
            channels.append('email')
        if self.sms_notifications:
            channels.append('sms')
        if self.push_notifications:
            channels.append('push')
        if self.whatsapp_notifications:
            channels.append('whatsapp')
        if self.telegram_notifications:
            channels.append('telegram')
        return channels
    
    def should_send_notification(self, notification_type, channel):
        """Check if notification should be sent based on preferences."""
        if not getattr(self, f"{notification_type}_notifications", True):
            return False
        
        if not getattr(self, f"{channel}_notifications", False):
            return False
        
        if self.quiet_hours_enabled and self.quiet_hours_start and self.quiet_hours_end:
            now = timezone.now().time()
            if self.quiet_hours_start <= now <= self.quiet_hours_end:
                return False
        
        return True


class EmailVerification(models.Model):
    """Email verification tokens."""
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='email_verifications')
    token = models.CharField(max_length=64, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    verified_at = models.DateTimeField(null=True, blank=True)
    is_used = models.BooleanField(default=False)
    
    class Meta:
        verbose_name = 'Email Verification'
        verbose_name_plural = 'Email Verifications'
        indexes = [
            models.Index(fields=['token']),
            models.Index(fields=['expires_at']),
        ]
    
    def __str__(self):
        return f"Email verification for {self.user.email}"
    
    def is_valid(self):
        """Check if verification token is valid."""
        return not self.is_used and self.expires_at > timezone.now()
    
    def verify(self):
        """Mark token as verified."""
        self.is_used = True
        self.verified_at = timezone.now()
        self.save(update_fields=['is_used', 'verified_at'])
        
        # Mark user email as verified
        self.user.verify_email()


class PasswordReset(models.Model):
    """Password reset tokens."""
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='password_resets')
    token = models.CharField(max_length=64, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    is_used = models.BooleanField(default=False)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    
    class Meta:
        verbose_name = 'Password Reset'
        verbose_name_plural = 'Password Resets'
        indexes = [
            models.Index(fields=['token']),
            models.Index(fields=['expires_at']),
        ]
    
    def __str__(self):
        return f"Password reset for {self.user.email}"
    
    def is_valid(self):
        """Check if reset token is valid."""
        return not self.is_used and self.expires_at > timezone.now()
    
    def mark_used(self):
        """Mark token as used."""
        self.is_used = True
        self.used_at = timezone.now()
        self.save(update_fields=['is_used', 'used_at'])


class UserDevice(models.Model):
    """Track user devices for security."""
    
    DEVICE_TYPES = (
        ('mobile', 'Mobile'),
        ('tablet', 'Tablet'),
        ('desktop', 'Desktop'),
        ('other', 'Other'),
    )
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='devices')
    device_id = models.CharField(max_length=255, unique=True, db_index=True)
    device_type = models.CharField(max_length=20, choices=DEVICE_TYPES)
    device_name = models.CharField(max_length=255)
    browser = models.CharField(max_length=100)
    browser_version = models.CharField(max_length=50)
    operating_system = models.CharField(max_length=100)
    os_version = models.CharField(max_length=50)
    ip_address = models.GenericIPAddressField()
    location = models.CharField(max_length=255, blank=True)
    last_login = models.DateTimeField()
    is_trusted = models.BooleanField(default=False)
    is_current = models.BooleanField(default=False)
    push_notification_token = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'User Device'
        verbose_name_plural = 'User Devices'
        ordering = ['-last_login']
        unique_together = ['user', 'device_id']
    
    def __str__(self):
        return f"{self.device_name} ({self.device_type}) - {self.user.email}"
    
    def mark_trusted(self):
        """Mark device as trusted."""
        self.is_trusted = True
        self.save(update_fields=['is_trusted'])

class EmailOTP(models.Model):
    """Email OTP for 2FA"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='email_otps')
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    
    class Meta:
        indexes = [
            models.Index(fields=['user', 'code']),
            models.Index(fields=['expires_at']),
        ]
    
    def __str__(self):
        return f"OTP for {self.user.email} - {self.code}"
    
    def is_valid(self):
        return not self.is_used and self.expires_at > timezone.now()
    
    def verify(self):
        self.is_used = True
        self.save()

class AuditLog(models.Model):
    """Audit log for user actions."""
    
    ACTION_TYPES = (
        ('create', 'Create'),
        ('update', 'Update'),
        ('delete', 'Delete'),
        ('view', 'View'),
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('payment', 'Payment'),
        ('booking', 'Booking'),
        ('export', 'Export'),
        ('import', 'Import'),
    )
    
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='audit_logs')
    action_type = models.CharField(max_length=20, choices=ACTION_TYPES)
    model_name = models.CharField(max_length=100)
    object_id = models.CharField(max_length=100, blank=True)
    object_repr = models.CharField(max_length=200, blank=True)
    changes = models.JSONField(default=dict)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        verbose_name = 'Audit Log'
        verbose_name_plural = 'Audit Logs'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['action_type', 'timestamp']),
            models.Index(fields=['model_name', 'object_id']),
        ]
    
    def __str__(self):
        return f"{self.action_type} by {self.user} at {self.timestamp}"

