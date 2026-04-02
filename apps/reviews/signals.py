from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from .models import Review, Testimonial, ReviewSummary
from apps.bookings.models import Booking
from django.db.models import Avg
import logging

logger = logging.getLogger(__name__)

@receiver(post_save, sender=Review)
def update_aircraft_rating(sender, instance, **kwargs):
    """Update aircraft's average rating when review is approved"""
    if instance.status == 'approved' and instance.aircraft:
        instance.update_aircraft_rating()
        logger.info(f"Updated aircraft {instance.aircraft.registration_number} rating")

@receiver(post_save, sender=Review)
def create_testimonial_from_review(sender, instance, created, **kwargs):
    """Create testimonial from high-rated reviews"""
    if instance.status == 'approved' and instance.overall_rating >= 4:
        # Check if testimonial already exists
        if not Testimonial.objects.filter(review=instance).exists():
            Testimonial.objects.create(
                review=instance,
                user=instance.user,
                customer_name=instance.display_name,
                content=instance.content,
                rating=instance.overall_rating,
                is_verified=instance.is_verified,
                is_featured=instance.overall_rating >= 5  # Auto-feature 5-star reviews
            )
            logger.info(f"Created testimonial from review {instance.review_number}")

@receiver(post_save, sender=Booking)
def request_review_on_completion(sender, instance, **kwargs):
    """Send review request when booking is completed OR when departure date has passed"""
    should_send_review = False
    
    # Case 1: Booking was just completed
    if instance.status == 'completed':
        # Check if review already exists
        if not Review.objects.filter(booking=instance).exists():
            should_send_review = True
    
    # Case 2: Departure date has passed and booking hasn't been reviewed yet
    elif instance.departure_datetime and instance.departure_datetime < timezone.now():
        # Flight date has passed, allow review
        if instance.status not in ['cancelled'] and not Review.objects.filter(booking=instance).exists():
            should_send_review = True
    
    if should_send_review:
        # Send email requesting review
        from django.core.mail import send_mail
        from django.conf import settings
        
        review_url = f"{settings.SITE_URL}/reviews/create/{instance.id}/"
        
        send_mail(
            f"Share your experience! Review your booking {instance.booking_reference}",
            f"Thank you for flying with FlynJet. Please take a moment to share your experience.\n\n{review_url}",
            settings.DEFAULT_FROM_EMAIL,
            [instance.user.email],
            fail_silently=False,
        )
        logger.info(f"Review request sent for booking {instance.booking_reference}")


@receiver(post_save, sender=Review)
def check_for_inappropriate_content(sender, instance, **kwargs):
    """Auto-flag potentially inappropriate reviews"""
    if instance.status == 'pending':
        # Check for inappropriate words
        inappropriate_words = ['spam', 'fake', 'scam', 'fraud', 'illegal']
        content_lower = instance.content.lower()
        
        for word in inappropriate_words:
            if word in content_lower:
                instance.report()
                logger.warning(f"Review {instance.review_number} auto-flagged for word: {word}")
                break

@receiver(post_save, sender=Review)
def update_review_summary(sender, instance, **kwargs):
    """Update review summary when review is approved"""
    if instance.status == 'approved' and instance.aircraft:
        # Calculate period
        today = timezone.now().date()
        start_of_month = today.replace(day=1)
        
        # Get or create summary
        summary, created = ReviewSummary.objects.get_or_create(
            aircraft=instance.aircraft,
            period_start=start_of_month,
            period_end=today,
            defaults={
                'total_reviews': 0,
                'average_rating': 0,
                'rating_5_count': 0,
                'rating_4_count': 0,
                'rating_3_count': 0,
                'rating_2_count': 0,
                'rating_1_count': 0
            }
        )
        
        # Update counts
        reviews = Review.objects.filter(
            aircraft=instance.aircraft,
            status='approved',
            created_at__date__gte=start_of_month
        )
        
        summary.total_reviews = reviews.count()
        summary.average_rating = reviews.aggregate(Avg('overall_rating'))['overall_rating__avg'] or 0
        summary.rating_5_count = reviews.filter(overall_rating=5).count()
        summary.rating_4_count = reviews.filter(overall_rating=4).count()
        summary.rating_3_count = reviews.filter(overall_rating=3).count()
        summary.rating_2_count = reviews.filter(overall_rating=2).count()
        summary.rating_1_count = reviews.filter(overall_rating=1).count()
        
        summary.save()
        logger.info(f"Updated review summary for aircraft {instance.aircraft.registration_number}")

@receiver(pre_save, sender=Review)
def track_review_changes(sender, instance, **kwargs):
    """Track changes to review status"""
    if instance.pk:
        try:
            old = Review.objects.get(pk=instance.pk)
            if old.status != instance.status:
                logger.info(f"Review {instance.review_number} status changed: {old.status} -> {instance.status}")
                
                # Notify user of status change
                if instance.status == 'approved':
                    from django.core.mail import send_mail
                    from django.conf import settings
                    
                    send_mail(
                        "Your review has been approved",
                        f"Your review for {instance.aircraft} has been published.",
                        settings.DEFAULT_FROM_EMAIL,
                        [instance.user.email],
                        fail_silently=False,
                    )
        except Review.DoesNotExist:
            pass

