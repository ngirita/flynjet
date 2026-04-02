import json
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, TemplateView
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from .models import LoyaltyAccount, LoyaltyTransaction, Promotion, Referral
from apps.bookings.models import Booking
from django.core.mail import EmailMultiAlternatives

class LoyaltyDashboardView(LoginRequiredMixin, TemplateView):
    """Loyalty program dashboard"""
    template_name = 'marketing/loyalty.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get or create loyalty account
        account, created = LoyaltyAccount.objects.get_or_create(
            user=self.request.user,
            defaults={'program_id': 1}  # Default program
        )
        
        # Get recent transactions
        transactions = account.transactions.all().order_by('-created_at')[:10]
        
        # Calculate tier progress
        next_tier = self.get_next_tier(account.current_tier)
        if next_tier:
            current_threshold = self.get_tier_threshold(account.current_tier)
            next_threshold = self.get_tier_threshold(next_tier)
            progress = ((account.lifetime_points - current_threshold) / 
                       (next_threshold - current_threshold)) * 100
            account.tier_progress = min(100, progress)
        
        context['account'] = account
        context['transactions'] = transactions
        context['next_tier'] = next_tier if account.tier_progress < 100 else None
        context['points_value'] = float(account.points_balance) / 100  # Example: 100 points = $1
        
        return context
    
    def get_tier_threshold(self, tier):
        thresholds = {
            'bronze': 0,
            'silver': 10000,
            'gold': 50000,
            'platinum': 100000,
            'diamond': 250000
        }
        return thresholds.get(tier, 0)
    
    def get_next_tier(self, current_tier):
        tiers = ['bronze', 'silver', 'gold', 'platinum', 'diamond']
        try:
            current_index = tiers.index(current_tier)
            if current_index < len(tiers) - 1:
                return tiers[current_index + 1]
        except ValueError:
            pass
        return None


class PromotionListView(ListView):
    """List active promotions"""
    model = Promotion
    template_name = 'marketing/promotions.html'
    context_object_name = 'promotions'
    
    def get_queryset(self):
        now = timezone.now()
        return Promotion.objects.filter(
            is_active=True,
            start_date__lte=now,
            end_date__gte=now
        ).order_by('end_date')


@csrf_exempt
def apply_promotion(request, code):
    """Apply promotion code to booking"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Login required'}, status=401)
    
    booking_id = request.POST.get('booking_id')
    booking = get_object_or_404(Booking, id=booking_id, user=request.user)
    
    try:
        promotion = Promotion.objects.get(promotion_code=code.upper(), is_active=True)
        
        if promotion.is_valid(request.user, booking):
            promotion.apply(booking)
            
            return JsonResponse({
                'status': 'success',
                'discount': float(booking.discount_amount_usd),
                'new_total': float(booking.total_amount_usd)
            })
        else:
            return JsonResponse({'error': 'Promotion not valid'}, status=400)
            
    except Promotion.DoesNotExist:
        return JsonResponse({'error': 'Invalid promotion code'}, status=404)


class ReferralDashboardView(LoginRequiredMixin, TemplateView):
    """Referral program dashboard"""
    template_name = 'marketing/referrals.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get referrals
        referrals = Referral.objects.filter(referrer=self.request.user).order_by('-created_at')
        
        # Calculate stats
        total_referrals = referrals.count()
        completed = referrals.filter(status='completed').count()
        pending = referrals.filter(status='pending').count()
        points_earned = sum(r.referrer_reward for r in referrals.filter(status='completed'))
        
        # Generate referral link
        base_url = self.request.build_absolute_uri('/')
        context['referral_link'] = f"{base_url}?ref={self.request.user.id}"
        
        context['referrals'] = referrals
        context['stats'] = {
            'total': total_referrals,
            'completed': completed,
            'pending': pending,
            'points_earned': points_earned
        }
        
        return context


@csrf_exempt
def share_referral(request):
    """Share referral via email"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Login required'}, status=401)
    
    email = request.POST.get('email')
    
    if not email:
        return JsonResponse({'error': 'Email required'}, status=400)
    
    # Create referral
    referral, created = Referral.objects.get_or_create(
        referrer=request.user,
        referred_email=email,
        defaults={
            'referrer_reward': 1000,  # 1000 points for referrer
            'referred_reward': 500     # 500 points for new user
        }
    )
    
    if created:
        # Send referral email
        from django.core.mail import send_mail
        send_mail(
            f"{request.user.get_full_name()} invited you to FlynJet",
            f"Join FlynJet using this link and get {referral.referred_reward} bonus points!",
            'info@flynjet.com',
            [email],
            fail_silently=False,
        )
        
        return JsonResponse({'status': 'sent', 'referral_id': referral.id})
    
    return JsonResponse({'error': 'Referral already sent'}, status=400)