import uuid
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from .models import Referral, LoyaltyAccount
import logging

logger = logging.getLogger(__name__)

class ReferralManager:
    """Manage referral program"""
    
    REFERRER_REWARD = 1000  # Points for referrer
    REFERRED_REWARD = 500   # Points for new user
    
    @classmethod
    def create_referral(cls, referrer, referred_email):
        """Create a new referral"""
        # Check if already referred
        existing = Referral.objects.filter(
            referrer=referrer,
            referred_email=referred_email
        ).exists()
        
        if existing:
            logger.warning(f"Referral already exists: {referrer.email} -> {referred_email}")
            return None
        
        # Create referral
        referral = Referral.objects.create(
            referrer=referrer,
            referred_email=referred_email,
            referrer_reward=cls.REFERRER_REWARD,
            referred_reward=cls.REFERRED_REWARD
        )
        
        # Send invitation email
        cls.send_invitation(referral)
        
        logger.info(f"Referral created: {referrer.email} -> {referred_email}")
        return referral
    
    @classmethod
    def track_click(cls, referral_code):
        """Track referral link click"""
        try:
            referral = Referral.objects.get(referral_code=referral_code)
            referral.track_click()
            logger.info(f"Referral click tracked: {referral.referral_code}")
            return referral
        except Referral.DoesNotExist:
            logger.error(f"Referral code not found: {referral_code}")
            return None
    
    @classmethod
    def complete_referral(cls, referral_code, referred_user):
        """Complete referral when new user signs up"""
        try:
            referral = Referral.objects.get(referral_code=referral_code)
            
            if referral.status != 'pending':
                logger.warning(f"Referral {referral_code} already {referral.status}")
                return False
            
            referral.complete_referral(referred_user)
            
            # Issue rewards
            cls.issue_rewards(referral)
            
            logger.info(f"Referral completed: {referral.referrer.email} -> {referred_user.email}")
            return True
        except Referral.DoesNotExist:
            logger.error(f"Referral code not found: {referral_code}")
            return False
    
    @classmethod
    def issue_rewards(cls, referral):
        """Issue points for completed referral"""
        # Award points to referrer
        if referral.referrer_reward > 0:
            LoyaltyManager.award_points(
                referral.referrer,
                referral.referrer_reward,
                'referral',
                str(referral.id),
                f"Referral bonus for {referral.referred_email}"
            )
        
        # Award points to referred user
        if referral.referred_user and referral.referred_reward > 0:
            LoyaltyManager.award_points(
                referral.referred_user,
                referral.referred_reward,
                'referral',
                str(referral.id),
                f"Welcome bonus from {referral.referrer.email}"
            )
        
        referral.reward_issued_at = timezone.now()
        referral.save(update_fields=['reward_issued_at'])
        
        logger.info(f"Rewards issued for referral {referral.id}")
    
    @classmethod
    def send_invitation(cls, referral):
        """Send referral invitation email"""
        context = {
            'referrer': referral.referrer.get_full_name() or referral.referrer.email,
            'referral_code': referral.referral_code,
            'referrer_reward': referral.referrer_reward,
            'referred_reward': referral.referred_reward,
            'signup_url': f"{settings.SITE_URL}/signup/?ref={referral.referral_code}"
        }
        
        subject = f"{context['referrer']} invited you to join FlynJet!"
        
        html_message = render_to_string('emails/referral_invitation.html', context)
        plain_message = render_to_string('emails/referral_invitation.txt', context)
        
        send_mail(
            subject,
            plain_message,
            settings.DEFAULT_FROM_EMAIL,
            [referral.referred_email],
            html_message=html_message,
            fail_silently=False,
        )
    
    @classmethod
    def send_reminder(cls, referral):
        """Send reminder for pending referral"""
        if referral.status != 'pending':
            return
        
        context = {
            'referrer': referral.referrer.get_full_name() or referral.referrer.email,
            'referral_code': referral.referral_code,
            'signup_url': f"{settings.SITE_URL}/signup/?ref={referral.referral_code}"
        }
        
        subject = f"Reminder: {context['referrer']} is waiting for you on FlynJet!"
        
        send_mail(
            subject,
            f"Don't forget to join FlynJet using {context['referrer']}'s referral link: {context['signup_url']}",
            settings.DEFAULT_FROM_EMAIL,
            [referral.referred_email],
            fail_silently=False,
        )
        
        logger.info(f"Reminder sent for referral {referral.id}")
    
    @classmethod
    def get_referral_stats(cls, user):
        """Get referral statistics for user"""
        referrals = Referral.objects.filter(referrer=user)
        
        stats = {
            'total': referrals.count(),
            'pending': referrals.filter(status='pending').count(),
            'completed': referrals.filter(status='completed').count(),
            'expired': referrals.filter(status='expired').count(),
            'points_earned': referrals.filter(
                status='completed',
                reward_issued_at__isnull=False
            ).aggregate(total=models.Sum('referrer_reward'))['total'] or 0,
            'recent': referrals.order_by('-created_at')[:5]
        }
        
        return stats
    
    @classmethod
    def cleanup_expired(cls):
        """Mark expired referrals"""
        expired = Referral.objects.filter(
            status='pending',
            expires_at__lt=timezone.now()
        )
        
        count = expired.update(status='expired')
        logger.info(f"Marked {count} referrals as expired")
        return count

class ReferralAnalytics:
    """Analyze referral performance"""
    
    @classmethod
    def get_conversion_rate(cls, start_date=None, end_date=None):
        """Calculate referral conversion rate"""
        referrals = Referral.objects.all()
        
        if start_date:
            referrals = referrals.filter(created_at__date__gte=start_date)
        if end_date:
            referrals = referrals.filter(created_at__date__lte=end_date)
        
        total = referrals.count()
        if total == 0:
            return 0
        
        converted = referrals.filter(status='completed').count()
        return (converted / total) * 100
    
    @classmethod
    def get_top_referrers(cls, limit=10):
        """Get top referrers by successful referrals"""
        from django.db.models import Count
        
        return Referral.objects.filter(
            status='completed'
        ).values(
            'referrer__email',
            'referrer__first_name',
            'referrer__last_name'
        ).annotate(
            count=Count('id'),
            points=Sum('referrer_reward')
        ).order_by('-count')[:limit]
    
    @classmethod
    def get_referral_timeline(cls, days=30):
        """Get referral timeline for charting"""
        end_date = timezone.now().date()
        start_date = end_date - timezone.timedelta(days=days)
        
        timeline = []
        current_date = start_date
        
        while current_date <= end_date:
            daily = Referral.objects.filter(
                created_at__date=current_date
            ).count()
            
            timeline.append({
                'date': current_date,
                'count': daily
            })
            
            current_date += timezone.timedelta(days=1)
        
        return timeline