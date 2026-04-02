from rest_framework import serializers
from .models import LoyaltyAccount, LoyaltyTransaction, Promotion, Referral, Campaign

class LoyaltyTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = LoyaltyTransaction
        fields = ['id', 'transaction_type', 'points', 'source', 'description', 'created_at']


class LoyaltyAccountSerializer(serializers.ModelSerializer):
    recent_transactions = LoyaltyTransactionSerializer(source='transactions', many=True, read_only=True)
    
    class Meta:
        model = LoyaltyAccount
        fields = [
            'id', 'account_number', 'points_balance', 'lifetime_points',
            'current_tier', 'tier_progress', 'recent_transactions'
        ]


class PromotionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Promotion
        fields = [
            'id', 'promotion_code', 'name', 'description', 'promotion_type',
            'discount_percentage', 'discount_amount', 'points_multiplier',
            'bonus_points', 'start_date', 'end_date'
        ]


class ReferralSerializer(serializers.ModelSerializer):
    referred_email = serializers.EmailField()
    
    class Meta:
        model = Referral
        fields = [
            'id', 'referred_email', 'status', 'referrer_reward',
            'referred_reward', 'created_at', 'signed_up_at'
        ]
        read_only_fields = ['status', 'signed_up_at']


class CampaignSerializer(serializers.ModelSerializer):
    class Meta:
        model = Campaign
        fields = '__all__'