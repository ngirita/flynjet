from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model
from .models import Campaign, LoyaltyProgram, LoyaltyAccount, LoyaltyTransaction, Referral, Promotion
from apps.bookings.models import Booking
from apps.fleet.models import Aircraft, AircraftManufacturer

User = get_user_model()

class MarketingModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        
        self.program = LoyaltyProgram.objects.create(
            name='Test Program',
            program_type='points',
            points_per_dollar=1,
            started_at=timezone.now()
        )
    
    def test_create_campaign(self):
        campaign = Campaign.objects.create(
            name='Test Campaign',
            campaign_type='email',
            status='draft',
            start_date=timezone.now(),
            end_date=timezone.now() + timezone.timedelta(days=7),
            subject='Test Subject',
            content='Test Content'
        )
        
        self.assertEqual(campaign.campaign_number[:4], 'CAMP')
        self.assertEqual(campaign.status, 'draft')
    
    def test_loyalty_account(self):
        account = LoyaltyAccount.objects.create(
            user=self.user,
            program=self.program,
            current_tier='bronze'
        )
        
        self.assertEqual(account.points_balance, 0)
        self.assertEqual(account.current_tier, 'bronze')
        
        # Test adding points
        account.add_points(1000, 'test', 'Test points')
        self.assertEqual(account.points_balance, 1000)
        self.assertEqual(account.lifetime_points, 1000)
    
    def test_referral(self):
        referral = Referral.objects.create(
            referrer=self.user,
            referred_email='friend@example.com',
            referrer_reward=1000,
            referred_reward=500
        )
        
        self.assertEqual(referral.status, 'pending')
        self.assertIsNotNone(referral.referral_code)
        
        # Test completion
        new_user = User.objects.create_user(
            email='friend@example.com',
            password='testpass123'
        )
        
        referral.complete_referral(new_user)
        self.assertEqual(referral.status, 'completed')
        self.assertEqual(referral.referred_user, new_user)
    
    def test_promotion(self):
        promotion = Promotion.objects.create(
            name='Test Promotion',
            promotion_code='TEST20',
            promotion_type='discount',
            discount_percentage=20,
            start_date=timezone.now(),
            end_date=timezone.now() + timezone.timedelta(days=30),
            is_active=True
        )
        
        self.assertEqual(promotion.promotion_code, 'TEST20')
        self.assertTrue(promotion.is_valid())

class MarketingViewsTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.client.login(email='test@example.com', password='testpass123')
    
    def test_loyalty_dashboard_view(self):
        response = self.client.get(reverse('marketing:loyalty'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'marketing/loyalty.html')
    
    def test_promotions_list_view(self):
        response = self.client.get(reverse('marketing:promotions'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'marketing/promotions.html')
    
    def test_referrals_view(self):
        response = self.client.get(reverse('marketing:referrals'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'marketing/referrals.html')