from celery import shared_task
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from .models import Campaign, LoyaltyAccount, Referral, Promotion
from .campaigns import CampaignManager
from .loyalty import PointsExpiryManager
from .referrals import ReferralManager
import logging

logger = logging.getLogger(__name__)

@shared_task
def send_campaign(campaign_id):
    """Send a marketing campaign"""
    try:
        success = CampaignManager.execute_campaign(campaign_id)
        if success:
            logger.info(f"Campaign {campaign_id} sent successfully")
        else:
            logger.error(f"Failed to send campaign {campaign_id}")
        return success
    except Exception as e:
        logger.error(f"Error sending campaign {campaign_id}: {e}")
        return False

@shared_task
def process_points_expiry():
    """Process points expiry"""
    try:
        # Mark points for expiry
        marked = PointsExpiryManager.apply_expiry()
        
        # Process expired points
        expired = PointsExpiryManager.process_expired_points()
        
        logger.info(f"Points expiry processed: {marked} marked, {expired} expired")
        return {'marked': marked, 'expired': expired}
    except Exception as e:
        logger.error(f"Error processing points expiry: {e}")
        return False

@shared_task
def send_referral_reminders():
    """Send reminders for pending referrals"""
    try:
        pending = Referral.objects.filter(
            status='pending',
            created_at__lte=timezone.now() - timezone.timedelta(days=7)
        )
        
        for referral in pending:
            ReferralManager.send_reminder(referral)
        
        logger.info(f"Sent {pending.count()} referral reminders")
        return pending.count()
    except Exception as e:
        logger.error(f"Error sending referral reminders: {e}")
        return 0

@shared_task
def cleanup_expired_referrals():
    """Mark expired referrals"""
    try:
        count = ReferralManager.cleanup_expired()
        logger.info(f"Cleaned up {count} expired referrals")
        return count
    except Exception as e:
        logger.error(f"Error cleaning up referrals: {e}")
        return 0

@shared_task
def update_customer_segments():
    """Update customer segmentation"""
    try:
        from .segmentation import CustomerSegmenter
        CustomerSegmenter.segment_customers()
        logger.info("Customer segments updated")
        return True
    except Exception as e:
        logger.error(f"Error updating segments: {e}")
        return False

@shared_task
def generate_loyalty_report():
    """Generate monthly loyalty report"""
    try:
        from django.db.models import Sum, Count, Avg
        
        # Get all loyalty accounts
        accounts = LoyaltyAccount.objects.filter(is_active=True)
        
        report = {
            'total_members': accounts.count(),
            'total_points_issued': LoyaltyTransaction.objects.filter(
                transaction_type='earn'
            ).aggregate(Sum('points'))['points__sum'] or 0,
            'total_points_redeemed': LoyaltyTransaction.objects.filter(
                transaction_type='redeem'
            ).aggregate(Sum('points'))['points__sum'] or 0,
            'average_points_per_user': accounts.aggregate(Avg('points_balance'))['points_balance__avg'] or 0,
            'tier_distribution': {
                'bronze': accounts.filter(current_tier='bronze').count(),
                'silver': accounts.filter(current_tier='silver').count(),
                'gold': accounts.filter(current_tier='gold').count(),
                'platinum': accounts.filter(current_tier='platinum').count(),
                'diamond': accounts.filter(current_tier='diamond').count(),
            }
        }
        
        # Send report to admin
        send_mail(
            'Loyalty Program Monthly Report',
            f'Report generated: {report}',
            settings.DEFAULT_FROM_EMAIL,
            [settings.ADMIN_EMAIL],
            fail_silently=False,
        )
        
        logger.info("Loyalty report generated")
        return report
    except Exception as e:
        logger.error(f"Error generating loyalty report: {e}")
        return False

@shared_task
def activate_promotions():
    """Activate scheduled promotions"""
    try:
        now = timezone.now()
        promotions = Promotion.objects.filter(
            is_active=False,
            start_date__lte=now,
            end_date__gte=now
        )
        
        count = promotions.update(is_active=True)
        logger.info(f"Activated {count} promotions")
        return count
    except Exception as e:
        logger.error(f"Error activating promotions: {e}")
        return 0

@shared_task
def deactivate_expired_promotions():
    """Deactivate expired promotions"""
    try:
        now = timezone.now()
        promotions = Promotion.objects.filter(
            is_active=True,
            end_date__lt=now
        )
        
        count = promotions.update(is_active=False)
        logger.info(f"Deactivated {count} expired promotions")
        return count
    except Exception as e:
        logger.error(f"Error deactivating promotions: {e}")
        return 0

@shared_task
def send_birthday_emails():
    """Send birthday emails to customers"""
    try:
        from apps.accounts.models import User
        from datetime import datetime
        
        today = datetime.now().date()
        
        # Find users with birthday today
        users = User.objects.filter(
            date_of_birth__day=today.day,
            date_of_birth__month=today.month,
            is_active=True
        )
        
        for user in users:
            # Award bonus points
            from .loyalty import LoyaltyManager
            LoyaltyManager.award_points(
                user,
                500,
                'promotion',
                'birthday',
                "Happy Birthday! Enjoy 500 bonus points."
            )
            
            # Send birthday email
            send_mail(
                "Happy Birthday from FlynJet!",
                f"Dear {user.get_full_name()},\n\nHappy Birthday! We've added 500 bonus points to your account.\n\nBest regards,\nFlynJet Team",
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=False,
            )
        
        logger.info(f"Sent {users.count()} birthday emails")
        return users.count()
    except Exception as e:
        logger.error(f"Error sending birthday emails: {e}")
        return 0

@shared_task
def generate_campaign_report(campaign_id):
    """Generate detailed campaign report"""
    try:
        campaign = Campaign.objects.get(id=campaign_id)
        
        metrics = {
            'campaign_name': campaign.name,
            'type': campaign.get_campaign_type_display(),
            'sent': campaign.sent_count,
            'opens': campaign.opened_count,
            'clicks': campaign.clicked_count,
            'conversions': campaign.converted_count,
            'revenue': float(campaign.revenue_generated),
            'open_rate': (campaign.opened_count / campaign.sent_count * 100) if campaign.sent_count > 0 else 0,
            'click_rate': (campaign.clicked_count / campaign.sent_count * 100) if campaign.sent_count > 0 else 0,
            'conversion_rate': (campaign.converted_count / campaign.sent_count * 100) if campaign.sent_count > 0 else 0,
            'roi': ((campaign.revenue_generated - campaign.budget) / campaign.budget * 100) if campaign.budget > 0 else 0,
        }
        
        # Save report to file or send email
        report_text = "\n".join([f"{k}: {v}" for k, v in metrics.items()])
        
        send_mail(
            f"Campaign Report: {campaign.name}",
            report_text,
            settings.DEFAULT_FROM_EMAIL,
            [settings.MARKETING_EMAIL],
            fail_silently=False,
        )
        
        logger.info(f"Campaign report generated for {campaign_id}")
        return metrics
    except Campaign.DoesNotExist:
        logger.error(f"Campaign {campaign_id} not found")
        return False