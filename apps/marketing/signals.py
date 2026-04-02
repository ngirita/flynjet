from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from .models import LoyaltyAccount, LoyaltyTransaction, Referral, Campaign
from apps.bookings.models import Booking
from apps.accounts.models import User
import logging

logger = logging.getLogger(__name__)

@receiver(post_save, sender=Booking)
def award_points_for_booking(sender, instance, created, **kwargs):
    """Award loyalty points when booking is completed"""
    if instance.status == 'completed' and instance.payment_status == 'paid':
        from .loyalty import LoyaltyManager
        
        # Calculate points
        points = LoyaltyManager.calculate_points_for_booking(instance)
        
        if points > 0:
            # Award points
            LoyaltyManager.award_points(
                instance.user,
                points,
                'booking',
                str(instance.id),
                f"Points earned for booking {instance.booking_reference}"
            )
            
            logger.info(f"Awarded {points} points to {instance.user.email} for booking {instance.id}")

@receiver(post_save, sender=User)
def auto_enroll_loyalty(sender, instance, created, **kwargs):
    """Auto-enroll new users in loyalty program"""
    if created:
        from .loyalty import LoyaltyManager
        LoyaltyManager.enroll_user(instance)
        logger.info(f"Auto-enrolled {instance.email} in loyalty program")

@receiver(post_save, sender=Referral)
def track_referral_signup(sender, instance, created, **kwargs):
    """Track when referred user signs up"""
    if instance.referred_user and instance.status == 'pending':
        from .referrals import ReferralManager
        ReferralManager.complete_referral(instance.referral_code, instance.referred_user)
        logger.info(f"Referral completed via signal: {instance.referral_code}")

@receiver(post_save, sender=LoyaltyTransaction)
def update_account_balance(sender, instance, created, **kwargs):
    """Update account balance when transaction is created"""
    if created:
        account = instance.account
        if instance.transaction_type == 'earn':
            account.points_balance += instance.points
            account.lifetime_points += instance.points
        elif instance.transaction_type in ['redeem', 'expire']:
            account.points_balance -= instance.points
        
        account.last_activity = timezone.now()
        account.save(update_fields=['points_balance', 'lifetime_points', 'last_activity'])
        
        # Check for tier upgrade
        from .loyalty import LoyaltyManager
        LoyaltyManager.check_tier_upgrade(account)
        
        logger.info(f"Updated balance for account {account.id}")

@receiver(pre_save, sender=LoyaltyAccount)
def track_tier_changes(sender, instance, **kwargs):
    """Track when user tier changes"""
    if instance.pk:
        try:
            old = LoyaltyAccount.objects.get(pk=instance.pk)
            if old.current_tier != instance.current_tier:
                logger.info(f"User {instance.user.email} tier changed: {old.current_tier} -> {instance.current_tier}")
                
                # Award tier upgrade bonus
                if instance.current_tier != 'bronze':
                    instance.add_points(1000, 'tier_upgrade', f"Upgraded to {instance.current_tier}")
        except LoyaltyAccount.DoesNotExist:
            pass

@receiver(post_save, sender=Campaign)
def schedule_campaign(sender, instance, created, **kwargs):
    """Schedule campaign for sending"""
    if instance.status == 'scheduled' and instance.start_date > timezone.now():
        from .tasks import send_campaign
        # Calculate delay
        delay = (instance.start_date - timezone.now()).total_seconds()
        send_campaign.apply_async(args=[instance.id], countdown=delay)
        logger.info(f"Scheduled campaign {instance.id} for {instance.start_date}")

@receiver(post_save, sender=Booking)
def check_for_promotion_eligibility(sender, instance, created, **kwargs):
    """Check if booking qualifies for any promotions"""
    if created and instance.status == 'draft':
        from .models import Promotion
        
        # Find applicable promotions
        promotions = Promotion.objects.filter(
            is_active=True,
            start_date__lte=timezone.now(),
            end_date__gte=timezone.now()
        )
        
        applicable = []
        for promo in promotions:
            if promo.is_valid(instance.user, instance):
                applicable.append(promo)
        
        if applicable:
            # Store in session or metadata for later application
            if not instance.metadata:
                instance.metadata = {}
            instance.metadata['applicable_promotions'] = [str(p.id) for p in applicable]
            instance.save(update_fields=['metadata'])
            
            logger.info(f"Found {len(applicable)} applicable promotions for booking {instance.id}")

@receiver(post_save, sender=User)
def create_referral_code(sender, instance, created, **kwargs):
    """Create unique referral code for new users"""
    if created:
        import hashlib
        # Generate unique code based on email and timestamp
        code_str = f"{instance.email}{timezone.now().timestamp()}"
        referral_code = hashlib.md5(code_str.encode()).hexdigest()[:8].upper()
        
        if not instance.metadata:
            instance.metadata = {}
        instance.metadata['referral_code'] = referral_code
        instance.save(update_fields=['metadata'])
        
        logger.info(f"Created referral code {referral_code} for {instance.email}")