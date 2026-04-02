from django.utils import timezone
from django.core.mail import send_mass_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from .models import Campaign, Promotion
from apps.accounts.models import User
import logging

logger = logging.getLogger(__name__)

class CampaignManager:
    """Manage marketing campaigns"""
    
    @classmethod
    def execute_campaign(cls, campaign_id):
        """Execute a marketing campaign"""
        try:
            campaign = Campaign.objects.get(id=campaign_id)
            
            if campaign.status != 'active':
                logger.warning(f"Campaign {campaign.id} is not active")
                return False
            
            # Get target audience
            recipients = cls.get_target_audience(campaign.target_audience)
            
            if not recipients:
                logger.warning(f"No recipients for campaign {campaign.id}")
                return False
            
            # Send based on campaign type
            if campaign.campaign_type == 'email':
                cls.send_email_campaign(campaign, recipients)
            elif campaign.campaign_type == 'sms':
                cls.send_sms_campaign(campaign, recipients)
            elif campaign.campaign_type == 'push':
                cls.send_push_campaign(campaign, recipients)
            
            # Update campaign stats
            campaign.sent_count = len(recipients)
            campaign.status = 'completed'
            campaign.save()
            
            logger.info(f"Campaign {campaign.id} executed successfully")
            return True
            
        except Campaign.DoesNotExist:
            logger.error(f"Campaign {campaign_id} not found")
            return False
    
    @classmethod
    def get_target_audience(cls, criteria):
        """Get users matching targeting criteria"""
        queryset = User.objects.filter(is_active=True)
        
        # Filter by user type
        if criteria.get('user_types'):
            queryset = queryset.filter(user_type__in=criteria['user_types'])
        
        # Filter by booking history
        if criteria.get('min_bookings'):
            from django.db.models import Count
            queryset = queryset.annotate(
                booking_count=Count('bookings')
            ).filter(booking_count__gte=criteria['min_bookings'])
        
        # Filter by last activity
        if criteria.get('active_last_days'):
            from django.utils import timezone
            from datetime import timedelta
            cutoff = timezone.now() - timedelta(days=criteria['active_last_days'])
            queryset = queryset.filter(last_activity__gte=cutoff)
        
        # Filter by location
        if criteria.get('countries'):
            queryset = queryset.filter(country__in=criteria['countries'])
        
        return list(queryset.values_list('email', flat=True))
    
    @classmethod
    def send_email_campaign(cls, campaign, recipients):
        """Send email campaign"""
        # Prepare email content
        context = {
            'campaign': campaign,
            'site_url': settings.SITE_URL,
            'year': timezone.now().year
        }
        
        html_content = render_to_string(f'emails/campaigns/{campaign.template}.html', context)
        text_content = render_to_string(f'emails/campaigns/{campaign.template}.txt', context)
        
        # Create emails
        emails = []
        for recipient in recipients:
            email = EmailMultiAlternatives(
                campaign.subject,
                text_content,
                settings.DEFAULT_FROM_EMAIL,
                [recipient]
            )
            email.attach_alternative(html_content, "text/html")
            
            # Add tracking pixel
            tracking_pixel = f"<img src='{settings.SITE_URL}/api/v1/marketing/track/open/{campaign.id}/{recipient}/' width='1' height='1' />"
            email.attach_alternative(tracking_pixel, "text/html")
            
            emails.append(email)
        
        # Send in batches
        if emails:
            connection = emails[0].get_connection()
            connection.send_messages(emails)
    
    @classmethod
    def send_sms_campaign(cls, campaign, recipients):
        """Send SMS campaign"""
        # Implement SMS sending logic (Twilio, etc.)
        logger.info(f"SMS campaign {campaign.id} would send to {len(recipients)} recipients")
    
    @classmethod
    def send_push_campaign(cls, campaign, recipients):
        """Send push notification campaign"""
        # Implement push notification logic (Firebase, etc.)
        logger.info(f"Push campaign {campaign.id} would send to {len(recipients)} recipients")

class ABTestManager:
    """Manage A/B testing for campaigns"""
    
    @classmethod
    def setup_ab_test(cls, campaign, variant_a, variant_b, split_ratio=50):
        """Setup A/B test for campaign"""
        campaign.is_ab_test = True
        campaign.variant_a = variant_a
        campaign.variant_b = variant_b
        campaign.save()
        
        # Split audience
        audience = CampaignManager.get_target_audience(campaign.target_audience)
        split_point = int(len(audience) * split_ratio / 100)
        
        group_a = audience[:split_point]
        group_b = audience[split_point:]
        
        logger.info(f"A/B test setup for campaign {campaign.id}: {len(group_a)} in A, {len(group_b)} in B")
        return group_a, group_b
    
    @classmethod
    def analyze_results(cls, campaign):
        """Analyze A/B test results"""
        if not campaign.is_ab_test:
            return None
        
        # Calculate metrics for each variant
        results = {
            'variant_a': {
                'opens': 0,  # Would come from tracking
                'clicks': 0,
                'conversions': 0,
                'revenue': 0
            },
            'variant_b': {
                'opens': 0,
                'clicks': 0,
                'conversions': 0,
                'revenue': 0
            }
        }
        
        # Determine winner based on primary metric (conversion rate)
        rate_a = results['variant_a']['conversions'] / max(campaign.segment_size // 2, 1)
        rate_b = results['variant_b']['conversions'] / max(campaign.segment_size - campaign.segment_size // 2, 1)
        
        if rate_a > rate_b:
            campaign.winning_variant = 'A'
        elif rate_b > rate_a:
            campaign.winning_variant = 'B'
        else:
            campaign.winning_variant = 'tie'
        
        campaign.save()
        return results

class CampaignAnalytics:
    """Track and analyze campaign performance"""
    
    @classmethod
    def track_open(cls, campaign_id, recipient_email):
        """Track email open"""
        try:
            campaign = Campaign.objects.get(id=campaign_id)
            campaign.opened_count += 1
            campaign.save()
            logger.info(f"Open tracked for campaign {campaign_id}")
            return True
        except Campaign.DoesNotExist:
            logger.error(f"Campaign {campaign_id} not found")
            return False
    
    @classmethod
    def track_click(cls, campaign_id, recipient_email, url):
        """Track link click"""
        try:
            campaign = Campaign.objects.get(id=campaign_id)
            campaign.clicked_count += 1
            campaign.save()
            logger.info(f"Click tracked for campaign {campaign_id}: {url}")
            return True
        except Campaign.DoesNotExist:
            logger.error(f"Campaign {campaign_id} not found")
            return False
    
    @classmethod
    def track_conversion(cls, campaign_id, recipient_email, amount):
        """Track conversion"""
        try:
            campaign = Campaign.objects.get(id=campaign_id)
            campaign.converted_count += 1
            campaign.revenue_generated += amount
            campaign.save()
            logger.info(f"Conversion tracked for campaign {campaign_id}: ${amount}")
            return True
        except Campaign.DoesNotExist:
            logger.error(f"Campaign {campaign_id} not found")
            return False
    
    @classmethod
    def get_campaign_metrics(cls, campaign_id):
        """Get detailed campaign metrics"""
        try:
            campaign = Campaign.objects.get(id=campaign_id)
            
            metrics = {
                'sent': campaign.sent_count,
                'delivered': campaign.delivered_count,
                'opens': campaign.opened_count,
                'clicks': campaign.clicked_count,
                'conversions': campaign.converted_count,
                'revenue': campaign.revenue_generated,
                'open_rate': (campaign.opened_count / campaign.sent_count * 100) if campaign.sent_count > 0 else 0,
                'click_rate': (campaign.clicked_count / campaign.sent_count * 100) if campaign.sent_count > 0 else 0,
                'conversion_rate': (campaign.converted_count / campaign.sent_count * 100) if campaign.sent_count > 0 else 0,
                'roi': ((campaign.revenue_generated - campaign.budget) / campaign.budget * 100) if campaign.budget > 0 else 0
            }
            
            return metrics
        except Campaign.DoesNotExist:
            logger.error(f"Campaign {campaign_id} not found")
            return None