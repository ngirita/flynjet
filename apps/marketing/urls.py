from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from .api import CampaignViewSet, LoyaltyAccountViewSet, PromotionViewSet, ReferralViewSet

router = DefaultRouter()
router.register(r'campaigns', CampaignViewSet, basename='campaign')
router.register(r'loyalty', LoyaltyAccountViewSet, basename='loyalty')
router.register(r'promotions', PromotionViewSet, basename='promotion')
router.register(r'referrals', ReferralViewSet, basename='referral')

app_name = 'marketing'

urlpatterns = [
    # Web URLs
    path('loyalty/', views.LoyaltyDashboardView.as_view(), name='loyalty'),
    path('promotions/', views.PromotionListView.as_view(), name='promotions'),
    path('promotions/<str:code>/', views.apply_promotion, name='apply_promotion'),
    path('referrals/', views.ReferralDashboardView.as_view(), name='referrals'),
    path('referrals/share/', views.share_referral, name='share'),
    
    # API URLs
    path('api/', include(router.urls)),
]