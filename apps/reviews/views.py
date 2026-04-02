import json
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import ListView, DetailView, CreateView, TemplateView
from django.contrib import messages
from django.http import JsonResponse
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.db import models  # Add this import for Q objects
from .models import Review, Testimonial, ReviewVote, ReviewPhoto
from .forms import ReviewForm, ReviewPhotoForm
from apps.bookings.models import Booking
from apps.fleet.models import Aircraft

class ReviewListView(ListView):
    """Public review listing"""
    model = Review
    template_name = 'reviews/list.html'
    context_object_name = 'reviews'
    paginate_by = 12
    
    def get_queryset(self):
        queryset = Review.objects.filter(status__in=['approved', 'featured'])
        
        # Filter by aircraft
        aircraft_id = self.request.GET.get('aircraft')
        if aircraft_id:
            queryset = queryset.filter(aircraft_id=aircraft_id)
        
        # Filter by rating
        rating = self.request.GET.get('rating')
        if rating:
            queryset = queryset.filter(overall_rating=rating)
        
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.is_authenticated:
            # Find any booking that:
            # 1. Has departure date in the past OR is completed
            # 2. Has not been reviewed yet
            # 3. Has valid status (not cancelled unless flight happened)
            from django.db.models import Q
            
            latest_booking = Booking.objects.filter(
                user=self.request.user
            ).filter(
                # Flight date has passed OR status is completed
                Q(departure_datetime__lt=timezone.now()) | Q(status='completed')
            ).exclude(
                # Exclude cancelled bookings where flight hasn't happened yet
                Q(status='cancelled') & Q(departure_datetime__gte=timezone.now())
            ).exclude(
                # FIX: Use 'reviews' (plural) instead of 'review' (singular)
                reviews__isnull=False
            ).order_by('-departure_datetime').first()
            
            context['latest_eligible_booking'] = latest_booking
        return context

class CreateReviewView(LoginRequiredMixin, CreateView):
    """Create a new review"""
    model = Review
    form_class = ReviewForm
    template_name = 'reviews/create.html'
    
    def dispatch(self, request, *args, **kwargs):
        self.booking = get_object_or_404(Booking, id=kwargs['booking_id'], user=request.user)
        
        # Check if already reviewed
        if Review.objects.filter(booking=self.booking).exists():
            messages.error(request, "You have already reviewed this booking")
            return redirect('bookings:detail', pk=self.booking.id)
        
        # Allow reviews for ANY booking that has a valid status
        # Instead of requiring 'completed', allow for any status that indicates the flight happened
        valid_statuses = ['completed', 'in_progress', 'confirmed', 'paid']
        
        # If the departure date has passed, allow review
        if self.booking.departure_datetime and self.booking.departure_datetime < timezone.now():
            # Flight date has passed - allow review regardless of status
            return super().dispatch(request, *args, **kwargs)
        
        # For future flights, only allow if booking is completed
        if self.booking.status not in valid_statuses:
            messages.error(request, "You can only review bookings after your flight or if you had a confirmed booking.")
            return redirect('bookings:detail', pk=self.booking.id)
        
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['booking'] = self.booking
        context['photo_form'] = ReviewPhotoForm()
        return context
    
    def form_valid(self, form):
        form.instance.user = self.request.user
        form.instance.booking = self.booking
        form.instance.aircraft = self.booking.aircraft
        form.instance.display_name = self.request.user.get_full_name() or self.request.user.email
        form.instance.is_verified = True  # Automatically verified since they booked
        
        response = super().form_valid(form)
        
        # Handle photo uploads
        photos = self.request.FILES.getlist('photos')
        for photo in photos:
            ReviewPhoto.objects.create(
                review=self.object,
                image=photo
            )
        
        messages.success(self.request, "Thank you for your review! It will be published after moderation.")
        return response
    
    def get_success_url(self):
        return reverse_lazy('reviews:detail', kwargs={'pk': self.object.pk})


class ReviewDetailView(DetailView):
    """Review detail page"""
    model = Review
    template_name = 'reviews/detail.html'
    context_object_name = 'review'
    
    def get_queryset(self):
        # Allow users to view their own pending reviews
        if self.request.user.is_authenticated:
            # Show approved/featured reviews for everyone
            # AND show pending reviews that belong to the current user
            return Review.objects.filter(
                models.Q(status__in=['approved', 'featured']) |
                models.Q(status='pending', user=self.request.user)
            )
        # For anonymous users, only show approved/featured
        return Review.objects.filter(status__in=['approved', 'featured'])
    
    def get_object(self, queryset=None):
        """Get the review object with custom error handling"""
        try:
            return super().get_object(queryset)
        except Review.DoesNotExist:
            # If review doesn't exist, check if there's a booking with this ID
            from django.shortcuts import redirect
            from django.contrib import messages
            
            pk = self.kwargs.get('pk')
            try:
                # Try to find a booking with this ID
                booking = Booking.objects.get(id=pk)
                if self.request.user.is_authenticated and booking.user == self.request.user:
                    # Check if review exists for this booking
                    existing_review = Review.objects.filter(booking=booking).first()
                    if existing_review:
                        # Redirect to the actual review
                        return redirect('reviews:detail', pk=existing_review.pk)
                    else:
                        messages.info(self.request, "You haven't written a review for this booking yet. Write one now!")
                        return redirect('reviews:create', booking_id=booking.id)
            except (Booking.DoesNotExist, ValueError):
                pass
            
            messages.error(self.request, "The review you're looking for doesn't exist or hasn't been published yet.")
            from django.shortcuts import redirect
            return redirect('reviews:list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['related_reviews'] = Review.objects.filter(
            aircraft=self.object.aircraft,
            status='approved'
        ).exclude(id=self.object.id)[:3]
        return context


class TestimonialListView(ListView):
    """Public testimonials page"""
    model = Testimonial
    template_name = 'reviews/testimonials.html'
    context_object_name = 'testimonials'
    paginate_by = 12
    
    def get_queryset(self):
        return Testimonial.objects.filter(is_verified=True).order_by('-is_featured', '-created_at')


class ReviewModerationView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """Admin review moderation"""
    model = Review
    template_name = 'reviews/moderation.html'
    context_object_name = 'reviews'
    paginate_by = 20
    
    def test_func(self):
        user = self.request.user
        return user.is_staff or user.user_type == 'admin'
    
    def get_queryset(self):
        status = self.request.GET.get('status', 'pending')
        return Review.objects.filter(status=status).order_by('created_at')


@csrf_exempt
def vote_review(request, pk):
    """Vote on review helpfulness"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Login required'}, status=401)
    
    review = get_object_or_404(Review, pk=pk, status='approved')
    vote_type = request.POST.get('vote_type')
    
    if vote_type not in ['helpful', 'not_helpful']:
        return JsonResponse({'error': 'Invalid vote type'}, status=400)
    
    # Check if already voted
    vote, created = ReviewVote.objects.get_or_create(
        review=review,
        user=request.user,
        defaults={'vote_type': vote_type}
    )
    
    if not created:
        if vote.vote_type == vote_type:
            # Remove vote
            vote.delete()
            if vote_type == 'helpful':
                review.helpful_votes -= 1
            else:
                review.not_helpful_votes -= 1
        else:
            # Change vote
            if vote.vote_type == 'helpful':
                review.helpful_votes -= 1
                review.not_helpful_votes += 1
            else:
                review.not_helpful_votes -= 1
                review.helpful_votes += 1
            vote.vote_type = vote_type
            vote.save()
    else:
        # New vote
        if vote_type == 'helpful':
            review.helpful_votes += 1
        else:
            review.not_helpful_votes += 1
    
    review.save()
    
    return JsonResponse({
        'helpful': review.helpful_votes,
        'not_helpful': review.not_helpful_votes
    })


@csrf_exempt
def report_review(request, pk):
    """Report inappropriate review"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    review = get_object_or_404(Review, pk=pk)
    review.report()
    
    return JsonResponse({'status': 'reported'})


@csrf_exempt
def moderate_review(request, pk):
    """Moderate review (admin only)"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    if not (request.user.is_staff or request.user.user_type == 'admin'):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    review = get_object_or_404(Review, pk=pk)
    action = request.POST.get('action')
    reason = request.POST.get('reason', '')
    
    if action == 'approve':
        review.approve(request.user)
        if review.overall_rating >= 4:
            # Auto-feature high ratings
            Testimonial.objects.create(
                review=review,
                user=review.user,
                customer_name=review.display_name,
                content=review.content,
                rating=review.overall_rating,
                is_verified=True
            )
        messages.success(request, f"Review {review.review_number} approved")
    
    elif action == 'reject':
        review.reject(request.user, reason)
        messages.warning(request, f"Review {review.review_number} rejected")
    
    elif action == 'feature':
        review.feature()
        messages.success(request, f"Review {review.review_number} featured")
    
    return redirect('reviews:admin_list')