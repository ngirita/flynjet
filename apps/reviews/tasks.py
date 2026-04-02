from celery import shared_task
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from .models import Review, Testimonial, ReviewSummary
from apps.bookings.models import Booking
import logging

logger = logging.getLogger(__name__)

@shared_task
def send_review_reminders():
    """Send reminders to customers who haven't reviewed completed bookings"""
    # Get bookings completed 3 days ago that don't have reviews
    reminder_date = timezone.now() - timezone.timedelta(days=3)
    week_ago = timezone.now() - timezone.timedelta(days=7)
    
    bookings = Booking.objects.filter(
        status='completed',
        actual_arrival__lte=reminder_date,
        actual_arrival__gte=week_ago
    ).exclude(
        reviews__isnull=False
    )
    
    for booking in bookings:
        send_single_review_reminder.delay(booking.id)
    
    logger.info(f"Sent review reminders for {bookings.count()} bookings")
    return bookings.count()

@shared_task
def send_single_review_reminder(booking_id):
    """Send single review reminder"""
    try:
        booking = Booking.objects.get(id=booking_id)
        
        review_url = f"{settings.SITE_URL}/reviews/create/{booking.id}/"
        
        send_mail(
            f"Share your experience - Review your flight {booking.booking_reference}",
            f"""
            Dear {booking.user.get_full_name() or booking.user.email},
            
            Thank you for flying with FlynJet. We hope you enjoyed your flight.
            
            Your feedback is valuable to us and helps other travelers make informed decisions.
            Would you take a moment to share your experience?
            
            {review_url}
            
            Best regards,
            FlynJet Team
            """,
            settings.DEFAULT_FROM_EMAIL,
            [booking.user.email],
            fail_silently=False,
        )
        
        logger.info(f"Review reminder sent for booking {booking_id}")
        return True
    except Booking.DoesNotExist:
        logger.error(f"Booking {booking_id} not found")
        return False

@shared_task
def generate_review_summaries():
    """Generate weekly review summaries"""
    today = timezone.now().date()
    week_ago = today - timezone.timedelta(days=7)
    
    from apps.fleet.models import Aircraft
    
    for aircraft in Aircraft.objects.filter(is_active=True):
        reviews = Review.objects.filter(
            aircraft=aircraft,
            status='approved',
            created_at__date__gte=week_ago
        )
        
        if reviews.exists():
            summary, created = ReviewSummary.objects.get_or_create(
                aircraft=aircraft,
                period_start=week_ago,
                period_end=today,
                defaults={
                    'total_reviews': reviews.count(),
                    'average_rating': reviews.aggregate(models.Avg('overall_rating'))['overall_rating__avg'] or 0,
                    'rating_5_count': reviews.filter(overall_rating=5).count(),
                    'rating_4_count': reviews.filter(overall_rating=4).count(),
                    'rating_3_count': reviews.filter(overall_rating=3).count(),
                    'rating_2_count': reviews.filter(overall_rating=2).count(),
                    'rating_1_count': reviews.filter(overall_rating=1).count(),
                }
            )
            
            logger.info(f"Generated review summary for aircraft {aircraft.registration_number}")
    
    return True

@shared_task
def moderate_review_queue():
    """Auto-moderate pending reviews"""
    pending_reviews = Review.objects.filter(status='pending')
    
    moderated = 0
    for review in pending_reviews:
        # Auto-approve reviews from verified customers with complete profiles
        if review.user.email_verified and review.user.profile:
            # Check for inappropriate content (simplified)
            inappropriate = False
            bad_words = ['spam', 'fake', 'scam']
            for word in bad_words:
                if word in review.content.lower():
                    inappropriate = True
                    break
            
            if not inappropriate and review.overall_rating >= 3:
                review.approve(None)  # Auto-approve
                moderated += 1
    
    logger.info(f"Auto-moderated {moderated} reviews")
    return moderated

@shared_task
def generate_review_report(days=30):
    """Generate review statistics report"""
    start_date = timezone.now() - timezone.timedelta(days=days)
    
    reviews = Review.objects.filter(created_at__gte=start_date)
    
    report = {
        'period_days': days,
        'total_reviews': reviews.count(),
        'avg_rating': reviews.aggregate(models.Avg('overall_rating'))['overall_rating__avg'] or 0,
        'by_status': dict(reviews.values_list('status').annotate(count=models.Count('id'))),
        'by_rating': {
            '5': reviews.filter(overall_rating=5).count(),
            '4': reviews.filter(overall_rating=4).count(),
            '3': reviews.filter(overall_rating=3).count(),
            '2': reviews.filter(overall_rating=2).count(),
            '1': reviews.filter(overall_rating=1).count(),
        },
        'helpful_votes': reviews.aggregate(total=models.Sum('helpful_votes'))['total'] or 0,
        'featured_testimonials': Testimonial.objects.filter(
            created_at__gte=start_date,
            is_featured=True
        ).count(),
    }
    
    logger.info(f"Review report generated: {report}")
    return report

@shared_task
def cleanup_old_reports(days=90):
    """Delete old review reports"""
    cutoff = timezone.now() - timezone.timedelta(days=days)
    old_summaries = ReviewSummary.objects.filter(period_end__lt=cutoff)
    
    count = old_summaries.count()
    old_summaries.delete()
    
    logger.info(f"Cleaned up {count} old review summaries")
    return count