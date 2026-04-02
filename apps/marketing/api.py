from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from .models import LoyaltyAccount, LoyaltyTransaction, Promotion, Referral, Campaign
from .serializers import (
    LoyaltyAccountSerializer, LoyaltyTransactionSerializer,
    PromotionSerializer, ReferralSerializer, CampaignSerializer
)

class LoyaltyAccountViewSet(viewsets.ReadOnlyModelViewSet):
    """API for loyalty accounts"""
    serializer_class = LoyaltyAccountSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return LoyaltyAccount.objects.filter(user=self.request.user)
    
    @action(detail=False, methods=['get'])
    def points_balance(self, request):
        """Get current points balance"""
        account = LoyaltyAccount.objects.get(user=request.user)
        return Response({
            'points': account.points_balance,
            'lifetime_points': account.lifetime_points,
            'tier': account.current_tier
        })
    
    @action(detail=False, methods=['get'])
    def transactions(self, request):
        """Get points transaction history"""
        account = LoyaltyAccount.objects.get(user=request.user)
        transactions = account.transactions.all().order_by('-created_at')[:50]
        serializer = LoyaltyTransactionSerializer(transactions, many=True)
        return Response(serializer.data)


class PromotionViewSet(viewsets.ReadOnlyModelViewSet):
    """API for promotions"""
    serializer_class = PromotionSerializer
    permission_classes = [permissions.AllowAny]
    
    def get_queryset(self):
        now = timezone.now()
        return Promotion.objects.filter(
            is_active=True,
            start_date__lte=now,
            end_date__gte=now
        )
    
    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def validate(self, request, pk=None):
        """Validate promotion for current user"""
        promotion = self.get_object()
        booking_id = request.data.get('booking_id')
        
        from apps.bookings.models import Booking
        try:
            booking = Booking.objects.get(id=booking_id, user=request.user)
            is_valid = promotion.is_valid(request.user, booking)
            return Response({'valid': is_valid})
        except Booking.DoesNotExist:
            return Response({'error': 'Booking not found'}, status=404)


class ReferralViewSet(viewsets.ModelViewSet):
    """API for referrals"""
    serializer_class = ReferralSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return Referral.objects.filter(referrer=self.request.user)
    
    def perform_create(self, serializer):
        serializer.save(referrer=self.request.user)
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get referral statistics"""
        referrals = self.get_queryset()
        
        return Response({
            'total': referrals.count(),
            'completed': referrals.filter(status='completed').count(),
            'pending': referrals.filter(status='pending').count(),
            'points_earned': sum(r.referrer_reward for r in referrals.filter(status='completed'))
        })


class CampaignViewSet(viewsets.ReadOnlyModelViewSet):
    """API for marketing campaigns"""
    serializer_class = CampaignSerializer
    permission_classes = [permissions.IsAdminUser]
    queryset = Campaign.objects.all().order_by('-created_at')