from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.marketing.api import CampaignViewSet, LoyaltyAccountViewSet, PromotionViewSet, ReferralViewSet

router = DefaultRouter()
router.register(r'campaigns', CampaignViewSet, basename='campaign')
router.register(r'loyalty', LoyaltyAccountViewSet, basename='loyalty')
router.register(r'promotions', PromotionViewSet, basename='promotion')
router.register(r'referrals', ReferralViewSet, basename='referral')

urlpatterns = [
    path('', include(router.urls)),
]