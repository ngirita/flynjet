from django.utils import timezone
from django.db import transaction
from django.conf import settings  # Add this import
from .models import LoyaltyProgram, LoyaltyAccount, LoyaltyTransaction
import logging

logger = logging.getLogger(__name__)

class LoyaltyManager:
    """Manage loyalty program operations"""
    
    @classmethod
    def enroll_user(cls, user, program_id=None):
        """Enroll user in loyalty program"""
        if not program_id:
            # Get default program
            program = LoyaltyProgram.objects.filter(is_active=True).first()
            if not program:
                logger.error("No active loyalty program found")
                return None
        else:
            try:
                program = LoyaltyProgram.objects.get(id=program_id, is_active=True)
            except LoyaltyProgram.DoesNotExist:
                logger.error(f"Loyalty program {program_id} not found")
                return None
        
        # Check if already enrolled
        if LoyaltyAccount.objects.filter(user=user).exists():
            logger.info(f"User {user.email} already enrolled in loyalty program")
            return LoyaltyAccount.objects.get(user=user)
        
        # Create account
        account = LoyaltyAccount.objects.create(
            user=user,
            program=program,
            current_tier='bronze'
        )
        
        # Award welcome bonus
        account.add_points(500, 'promotion', 'Welcome bonus')
        
        logger.info(f"User {user.email} enrolled in loyalty program")
        return account
    
    @classmethod
    def award_points(cls, user, points, source, source_id=None, description=""):
        """Award points to user"""
        try:
            account = LoyaltyAccount.objects.get(user=user, is_active=True)
        except LoyaltyAccount.DoesNotExist:
            # Auto-enroll if not enrolled
            account = cls.enroll_user(user)
            if not account:
                return False
        
        account.add_points(points, source, source_id)
        
        if description:
            # Update last transaction description
            transaction = account.transactions.latest('created_at')
            transaction.description = description
            transaction.save()
        
        logger.info(f"Awarded {points} points to {user.email} for {source}")
        return True
    
    @classmethod
    def redeem_points(cls, user, points, source, source_id=None):
        """Redeem points from user account"""
        try:
            account = LoyaltyAccount.objects.get(user=user, is_active=True)
        except LoyaltyAccount.DoesNotExist:
            logger.error(f"User {user.email} not enrolled in loyalty program")
            return False
        
        if account.points_balance < points:
            logger.warning(f"User {user.email} has insufficient points: {account.points_balance} < {points}")
            return False
        
        account.redeem_points(points, source, source_id)
        logger.info(f"Redeemed {points} points from {user.email} for {source}")
        return True
    
    @classmethod
    def calculate_points_for_booking(cls, booking):
        """Calculate points earned for booking"""
        try:
            account = LoyaltyAccount.objects.get(user=booking.user, is_active=True)
        except LoyaltyAccount.DoesNotExist:
            return 0
        
        # Base points: 1 point per dollar
        points = int(booking.total_amount_usd)
        
        # Tier multiplier
        multipliers = {
            'bronze': 1,
            'silver': 1.25,
            'gold': 1.5,
            'platinum': 2,
            'diamond': 3
        }
        multiplier = multipliers.get(account.current_tier, 1)
        
        points = int(points * multiplier)
        
        # Apply any active promotions
        from .models import Promotion
        active_promos = Promotion.objects.filter(
            is_active=True,
            start_date__lte=timezone.now(),
            end_date__gte=timezone.now()
        )
        
        for promo in active_promos:
            if promo.promotion_type == 'points_multiplier' and promo.points_multiplier:
                points = int(points * promo.points_multiplier)
            elif promo.promotion_type == 'bonus_points' and promo.bonus_points:
                points += promo.bonus_points
        
        return points
    
    @classmethod
    def get_tier_benefits(cls, tier):
        """Get benefits for specific tier"""
        benefits = {
            'bronze': [
                '1 point per $1 spent',
                'Priority check-in'
            ],
            'silver': [
                '1.25 points per $1 spent',
                'Priority check-in',
                'Lounge access (domestic)'
            ],
            'gold': [
                '1.5 points per $1 spent',
                'Priority check-in',
                'Lounge access (international)',
                'Free seat selection'
            ],
            'platinum': [
                '2 points per $1 spent',
                'Priority check-in',
                'Lounge access (all)',
                'Free seat selection',
                'Priority boarding'
            ],
            'diamond': [
                '3 points per $1 spent',
                'Priority check-in',
                'Lounge access (all)',
                'Free seat selection',
                'Priority boarding',
                'Complimentary upgrades'
            ]
        }
        return benefits.get(tier, [])
    
    @classmethod
    def get_next_tier(cls, current_tier):
        """Get next tier name"""
        tiers = ['bronze', 'silver', 'gold', 'platinum', 'diamond']
        try:
            current_index = tiers.index(current_tier)
            if current_index < len(tiers) - 1:
                return tiers[current_index + 1]
        except ValueError:
            pass
        return None
    
    @classmethod
    def get_tier_threshold(cls, tier):
        """Get points threshold for tier"""
        thresholds = {
            'bronze': 0,
            'silver': 10000,
            'gold': 50000,
            'platinum': 100000,
            'diamond': 250000
        }
        return thresholds.get(tier, 0)
    
    @classmethod
    def calculate_tier_progress(cls, account):
        """Calculate progress to next tier"""
        next_tier = cls.get_next_tier(account.current_tier)
        if not next_tier:
            return 100  # Already at highest tier
        
        current_threshold = cls.get_tier_threshold(account.current_tier)
        next_threshold = cls.get_tier_threshold(next_tier)
        
        if next_threshold <= current_threshold:
            return 100
        
        progress = ((account.lifetime_points - current_threshold) / 
                   (next_threshold - current_threshold)) * 100
        return min(100, progress)
    
    @classmethod
    def check_tier_upgrade(cls, account):
        """Check if user qualifies for tier upgrade"""
        new_tier = account.current_tier
        
        for tier in ['silver', 'gold', 'platinum', 'diamond']:
            if account.lifetime_points >= cls.get_tier_threshold(tier):
                new_tier = tier
        
        if new_tier != account.current_tier:
            old_tier = account.current_tier
            account.current_tier = new_tier
            account.save(update_fields=['current_tier'])
            
            # Award tier upgrade bonus
            account.add_points(1000, 'tier_upgrade', f"Upgraded from {old_tier} to {new_tier}")
            
            logger.info(f"User {account.user.email} upgraded from {old_tier} to {new_tier}")
            return True
        
        return False

class PointsExpiryManager:
    """Manage points expiry"""
    
    @classmethod
    def apply_expiry(cls, months=12):
        """Apply expiry to points older than specified months"""
        cutoff = timezone.now() - timezone.timedelta(days=30 * months)
        
        # Find transactions older than cutoff
        old_transactions = LoyaltyTransaction.objects.filter(
            transaction_type='earn',
            created_at__lt=cutoff,
            expires_at__isnull=True
        )
        
        expired_points = 0
        for transaction in old_transactions:
            # Mark as expiring
            transaction.expires_at = timezone.now() + timezone.timedelta(days=30)
            transaction.save()
            
            # Create expiry warning
            cls.send_expiry_warning(transaction.account.user, transaction.points, transaction.expires_at)
            
            expired_points += transaction.points
        
        logger.info(f"Marked {expired_points} points for expiry")
        return expired_points
    
    @classmethod
    def process_expired_points(cls):
        """Process actually expired points"""
        expired = LoyaltyTransaction.objects.filter(
            expires_at__lt=timezone.now(),
            transaction_type='earn'
        )
        
        total_expired = 0
        for transaction in expired:
            # Create expiry transaction
            LoyaltyTransaction.objects.create(
                account=transaction.account,
                transaction_type='expire',
                points=transaction.points,
                source='expiry',
                description=f"Points expired from {transaction.created_at.date()}"
            )
            
            # Reduce balance
            account = transaction.account
            account.points_balance -= transaction.points
            account.save(update_fields=['points_balance'])
            
            total_expired += transaction.points
            transaction.delete()
        
        logger.info(f"Processed {total_expired} expired points")
        return total_expired
    
    @classmethod
    def send_expiry_warning(cls, user, points, expiry_date):
        """Send warning about points expiry"""
        from django.core.mail import send_mail
        
        days_left = (expiry_date - timezone.now()).days
        
        send_mail(
            "Your loyalty points are expiring soon",
            f"You have {points} points expiring in {days_left} days. Use them before they expire!",
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=False,
        )