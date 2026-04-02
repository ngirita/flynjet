import uuid
from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.core.models import TimeStampedModel
from apps.accounts.models import User
from apps.bookings.models import Booking

class Campaign(TimeStampedModel):
    """Marketing campaigns"""
    
    CAMPAIGN_TYPES = (
        ('email', 'Email Campaign'),
        ('sms', 'SMS Campaign'),
        ('push', 'Push Notification'),
        ('social', 'Social Media'),
        ('display', 'Display Ad'),
        ('referral', 'Referral Program'),
        ('loyalty', 'Loyalty Program'),
    )
    
    CAMPAIGN_STATUS = (
        ('draft', 'Draft'),
        ('scheduled', 'Scheduled'),
        ('active', 'Active'),
        ('paused', 'Paused'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    campaign_number = models.CharField(max_length=50, unique=True)
    
    # Basic Info
    name = models.CharField(max_length=200)
    campaign_type = models.CharField(max_length=20, choices=CAMPAIGN_TYPES)
    status = models.CharField(max_length=20, choices=CAMPAIGN_STATUS, default='draft')
    
    # Schedule
    start_date = models.DateTimeField()
    end_date = models.DateTimeField(null=True, blank=True)
    
    # Targeting
    target_audience = models.JSONField(default=dict, help_text="Targeting criteria")
    segment_size = models.IntegerField(default=0)
    
    # Content
    subject = models.CharField(max_length=200, blank=True)
    content = models.TextField()
    template = models.CharField(max_length=200, blank=True)
    
    # Media
    images = models.JSONField(default=list, blank=True)
    attachments = models.JSONField(default=list, blank=True)
    
    # Budget
    budget = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default='USD')
    
    # Performance
    sent_count = models.IntegerField(default=0)
    delivered_count = models.IntegerField(default=0)
    opened_count = models.IntegerField(default=0)
    clicked_count = models.IntegerField(default=0)
    converted_count = models.IntegerField(default=0)
    revenue_generated = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # A/B Testing
    is_ab_test = models.BooleanField(default=False)
    variant_a = models.JSONField(default=dict, blank=True)
    variant_b = models.JSONField(default=dict, blank=True)
    winning_variant = models.CharField(max_length=10, blank=True)
    
    # Metadata
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['campaign_number']),
            models.Index(fields=['status', 'start_date']),
            models.Index(fields=['campaign_type']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.get_campaign_type_display()})"
    
    def save(self, *args, **kwargs):
        if not self.campaign_number:
            self.campaign_number = self.generate_campaign_number()
        super().save(*args, **kwargs)
    
    def generate_campaign_number(self):
        import random
        import string
        timestamp = timezone.now().strftime('%Y%m')
        random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        return f"CAMP{timestamp}{random_str}"
    
    def launch(self):
        """Launch the campaign"""
        self.status = 'active'
        self.save(update_fields=['status'])
    
    def pause(self):
        """Pause the campaign"""
        self.status = 'paused'
        self.save(update_fields=['status'])
    
    def complete(self):
        """Mark campaign as completed"""
        self.status = 'completed'
        self.end_date = timezone.now()
        self.save(update_fields=['status', 'end_date'])
    
    def track_open(self):
        """Track email open"""
        self.opened_count += 1
        self.save(update_fields=['opened_count'])
    
    def track_click(self):
        """Track link click"""
        self.clicked_count += 1
        self.save(update_fields=['clicked_count'])
    
    def track_conversion(self, revenue=0):
        """Track conversion"""
        self.converted_count += 1
        if revenue:
            self.revenue_generated += revenue
        self.save(update_fields=['converted_count', 'revenue_generated'])
    
    def calculate_roi(self):
        """Calculate return on investment"""
        if self.budget == 0:
            return 0
        return (self.revenue_generated - self.budget) / self.budget * 100


class LoyaltyProgram(TimeStampedModel):
    """Customer loyalty program"""
    
    PROGRAM_TYPES = (
        ('points', 'Points Based'),
        ('tier', 'Tier Based'),
        ('hybrid', 'Hybrid'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    program_type = models.CharField(max_length=20, choices=PROGRAM_TYPES)
    
    # Points Configuration
    points_per_dollar = models.DecimalField(max_digits=5, decimal_places=2, default=1)
    minimum_points_redemption = models.IntegerField(default=1000)
    
    # Tiers
    tiers = models.JSONField(default=list, help_text="List of tiers and benefits")
    
    # Benefits
    benefits = models.JSONField(default=list)
    
    # Rules
    enrollment_rules = models.TextField(blank=True)
    earning_rules = models.TextField(blank=True)
    redemption_rules = models.TextField(blank=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return self.name
    
    def calculate_points(self, amount):
        """Calculate points earned for a transaction"""
        return int(float(amount) * float(self.points_per_dollar))
    
    def get_tier_benefits(self, tier_name):
        """Get benefits for a specific tier"""
        for tier in self.tiers:
            if tier.get('name') == tier_name:
                return tier.get('benefits', [])
        return []


class LoyaltyAccount(models.Model):
    """User loyalty account"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='loyalty_account')
    program = models.ForeignKey(LoyaltyProgram, on_delete=models.PROTECT)
    
    # Account Details
    account_number = models.CharField(max_length=50, unique=True)
    
    # Points
    points_balance = models.IntegerField(default=0)
    lifetime_points = models.IntegerField(default=0)
    
    # Tier
    current_tier = models.CharField(max_length=50, default='bronze')
    tier_progress = models.IntegerField(default=0, help_text="Progress to next tier")
    
    # Status
    is_active = models.BooleanField(default=True)
    enrolled_at = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['account_number']),
            models.Index(fields=['user']),
            models.Index(fields=['current_tier']),
        ]
    
    def __str__(self):
        return f"Loyalty Account {self.account_number} - {self.user.email}"
    
    def save(self, *args, **kwargs):
        if not self.account_number:
            self.account_number = self.generate_account_number()
        super().save(*args, **kwargs)
    
    def generate_account_number(self):
        import random
        import string
        random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
        return f"LY{random_str}"
    
    def add_points(self, points, source, source_id=None):
        """Add points to account"""
        self.points_balance += points
        self.lifetime_points += points
        self.last_activity = timezone.now()
        self.save(update_fields=['points_balance', 'lifetime_points', 'last_activity'])
        
        # Create transaction record
        LoyaltyTransaction.objects.create(
            account=self,
            transaction_type='earn',
            points=points,
            source=source,
            source_id=source_id
        )
        
        # Check for tier upgrade
        self.check_tier_upgrade()
    
    def redeem_points(self, points, source, source_id=None):
        """Redeem points from account"""
        if points > self.points_balance:
            raise ValueError("Insufficient points")
        
        self.points_balance -= points
        self.last_activity = timezone.now()
        self.save(update_fields=['points_balance', 'last_activity'])
        
        # Create transaction record
        LoyaltyTransaction.objects.create(
            account=self,
            transaction_type='redeem',
            points=points,
            source=source,
            source_id=source_id
        )
    
    def check_tier_upgrade(self):
        """Check if user qualifies for tier upgrade"""
        # Tier thresholds - in production, these would come from program config
        thresholds = {
            'bronze': 0,
            'silver': 10000,
            'gold': 50000,
            'platinum': 100000,
            'diamond': 250000
        }
        
        new_tier = 'bronze'
        for tier, threshold in thresholds.items():
            if self.lifetime_points >= threshold:
                new_tier = tier
        
        if new_tier != self.current_tier:
            self.current_tier = new_tier
            self.save(update_fields=['current_tier'])
            
            # Award welcome bonus for new tier
            if new_tier != 'bronze':
                self.add_points(1000, 'tier_upgrade', new_tier)


class LoyaltyTransaction(TimeStampedModel):
    """Points transactions"""
    
    TRANSACTION_TYPES = (
        ('earn', 'Points Earned'),
        ('redeem', 'Points Redeemed'),
        ('expire', 'Points Expired'),
        ('adjust', 'Manual Adjustment'),
        ('bonus', 'Bonus Points'),
    )
    
    SOURCE_TYPES = (
        ('booking', 'Flight Booking'),
        ('referral', 'Referral'),
        ('promotion', 'Promotion'),
        ('tier_upgrade', 'Tier Upgrade'),
        ('feedback', 'Feedback'),
        ('review', 'Review'),
        ('social', 'Social Media'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account = models.ForeignKey(LoyaltyAccount, on_delete=models.CASCADE, related_name='transactions')
    
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    points = models.IntegerField()
    
    source = models.CharField(max_length=50, choices=SOURCE_TYPES)
    source_id = models.CharField(max_length=100, blank=True)
    
    description = models.CharField(max_length=200, blank=True)
    
    # Reference
    booking = models.ForeignKey(Booking, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Expiry
    expires_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['account', '-created_at']),
            models.Index(fields=['transaction_type']),
        ]
    
    def __str__(self):
        return f"{self.get_transaction_type_display()}: {self.points} points"


class Referral(TimeStampedModel):
    """Referral program tracking"""
    
    REFERRAL_STATUS = (
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    referrer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='referrals_made')
    referred_email = models.EmailField()
    
    # Referred User (if they sign up)
    referred_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='referred_by')
    
    # Referral Code
    referral_code = models.CharField(max_length=50, unique=True)
    
    # Status
    status = models.CharField(max_length=20, choices=REFERRAL_STATUS, default='pending')
    
    # Rewards
    referrer_reward = models.IntegerField(default=0, help_text="Points awarded to referrer")
    referred_reward = models.IntegerField(default=0, help_text="Points awarded to referred user")
    
    # Tracking
    clicked_at = models.DateTimeField(null=True, blank=True)
    signed_up_at = models.DateTimeField(null=True, blank=True)
    first_booking_at = models.DateTimeField(null=True, blank=True)
    reward_issued_at = models.DateTimeField(null=True, blank=True)
    
    # Expiry
    expires_at = models.DateTimeField()
    
    class Meta:
        indexes = [
            models.Index(fields=['referral_code']),
            models.Index(fields=['referrer', 'status']),
            models.Index(fields=['referred_email']),
        ]
        unique_together = ['referrer', 'referred_email']
    
    def __str__(self):
        return f"Referral by {self.referrer.email} to {self.referred_email}"
    
    def save(self, *args, **kwargs):
        if not self.referral_code:
            self.referral_code = self.generate_referral_code()
        if not self.expires_at:
            self.expires_at = timezone.now() + timezone.timedelta(days=90)
        super().save(*args, **kwargs)
    
    def generate_referral_code(self):
        import random
        import string
        random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        return f"REF{random_str}"
    
    def track_click(self):
        """Track referral link click"""
        self.clicked_at = timezone.now()
        self.save(update_fields=['clicked_at'])
    
    def complete_referral(self, referred_user):
        """Mark referral as completed"""
        self.status = 'completed'
        self.referred_user = referred_user
        self.signed_up_at = timezone.now()
        self.save(update_fields=['status', 'referred_user', 'signed_up_at'])
    
    def issue_rewards(self):
        """Issue rewards for completed referral"""
        if self.reward_issued_at:
            return
        
        # Get loyalty accounts
        referrer_account = LoyaltyAccount.objects.get(user=self.referrer)
        
        # Issue points to referrer
        if self.referrer_reward > 0:
            referrer_account.add_points(
                self.referrer_reward,
                'referral',
                str(self.id)
            )
        
        # Issue points to referred user
        if self.referred_user and self.referred_reward > 0:
            referred_account = LoyaltyAccount.objects.get(user=self.referred_user)
            referred_account.add_points(
                self.referred_reward,
                'referral',
                str(self.id)
            )
        
        self.reward_issued_at = timezone.now()
        self.save(update_fields=['reward_issued_at'])


class Promotion(TimeStampedModel):
    """Special promotions and offers"""
    
    PROMOTION_TYPES = (
        ('discount', 'Discount'),
        ('points_multiplier', 'Points Multiplier'),
        ('bonus_points', 'Bonus Points'),
        ('upgrade', 'Free Upgrade'),
        ('gift', 'Gift'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    promotion_code = models.CharField(max_length=50, unique=True)
    
    # Basic Info
    name = models.CharField(max_length=200)
    description = models.TextField()
    promotion_type = models.CharField(max_length=20, choices=PROMOTION_TYPES)
    
    # Value
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    points_multiplier = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    bonus_points = models.IntegerField(null=True, blank=True)
    
    # Eligibility
    min_booking_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    min_passengers = models.IntegerField(null=True, blank=True)
    applicable_aircraft = models.JSONField(default=list, blank=True)
    applicable_routes = models.JSONField(default=list, blank=True)
    user_segments = models.JSONField(default=list, blank=True)
    
    # Usage
    max_uses_total = models.IntegerField(default=0, help_text="0 for unlimited")
    max_uses_per_user = models.IntegerField(default=1)
    current_uses = models.IntegerField(default=0)
    
    # Schedule
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    
    # Status
    is_active = models.BooleanField(default=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['promotion_code']),
            models.Index(fields=['start_date', 'end_date']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.promotion_code})"
    
    def is_valid(self, user=None, booking=None):
        """Check if promotion is valid"""
        now = timezone.now()
        
        # Check dates
        if now < self.start_date or now > self.end_date:
            return False
        
        # Check total usage limit
        if self.max_uses_total > 0 and self.current_uses >= self.max_uses_total:
            return False
        
        # Check user-specific limits
        if user and self.max_uses_per_user > 0:
            user_uses = PromotionUsage.objects.filter(
                promotion=self,
                user=user
            ).count()
            if user_uses >= self.max_uses_per_user:
                return False
        
        # Check booking requirements
        if booking:
            if self.min_booking_amount and booking.total_amount_usd < self.min_booking_amount:
                return False
            
            if self.min_passengers and booking.passenger_count < self.min_passengers:
                return False
            
            if self.applicable_aircraft and str(booking.aircraft.id) not in self.applicable_aircraft:
                return False
            
            route = f"{booking.departure_airport}-{booking.arrival_airport}"
            if self.applicable_routes and route not in self.applicable_routes:
                return False
        
        return True
    
    def apply(self, booking):
        """Apply promotion to booking"""
        if not self.is_valid(booking.user, booking):
            raise ValueError("Promotion is not valid")
        
        # Apply discount based on type
        if self.promotion_type == 'discount':
            if self.discount_percentage:
                discount = booking.total_amount_usd * (self.discount_percentage / 100)
                booking.discount_amount_usd += discount
            elif self.discount_amount:
                booking.discount_amount_usd += self.discount_amount
        
        booking.save()
        
        # Record usage
        PromotionUsage.objects.create(
            promotion=self,
            user=booking.user,
            booking=booking
        )
        
        self.current_uses += 1
        self.save(update_fields=['current_uses'])


class PromotionUsage(models.Model):
    """Track promotion usage"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    promotion = models.ForeignKey(Promotion, on_delete=models.CASCADE, related_name='usages')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, null=True, blank=True)
    
    used_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['promotion', 'user', 'booking']
        indexes = [
            models.Index(fields=['promotion', 'user']),
        ]
    
    def __str__(self):
        return f"Usage of {self.promotion.promotion_code} by {self.user.email}"