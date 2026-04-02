from django.utils import timezone
from .models import Review
from apps.bookings.models import Booking

class ReviewVerifier:
    """Verify review authenticity"""
    
    @classmethod
    def verify_booking(cls, review):
        """Verify that reviewer actually booked the flight"""
        if not review.booking:
            return False
        
        # Check if booking belongs to user
        if review.booking.user != review.user:
            return False
        
        # Check if booking was completed
        if review.booking.status != 'completed':
            return False
        
        return True
    
    @classmethod
    def verify_purchase(cls, review):
        """Verify that payment was made"""
        if not review.booking:
            return False
        
        # Check if booking was paid
        return review.booking.payment_status == 'paid'
    
    @classmethod
    def check_duplicate(cls, review):
        """Check for duplicate reviews"""
        # Same user, same aircraft
        existing = Review.objects.filter(
            user=review.user,
            aircraft=review.aircraft,
            status__in=['pending', 'approved']
        ).exclude(id=review.id)
        
        if existing.exists():
            return True
        
        # Same booking
        if review.booking:
            existing = Review.objects.filter(
                booking=review.booking
            ).exclude(id=review.id)
            if existing.exists():
                return True
        
        return False
    
    @classmethod
    def check_frequency(cls, user, hours=24):
        """Check if user is posting too many reviews"""
        recent = Review.objects.filter(
            user=user,
            created_at__gte=timezone.now() - timezone.timedelta(hours=hours)
        ).count()
        
        return recent >= 3  # Max 3 reviews per 24 hours
    
    @classmethod
    def verify_identity(cls, review):
        """Verify reviewer identity"""
        user = review.user
        
        # Check if email is verified
        if not user.email_verified:
            return False
        
        # Check if profile is complete
        profile = getattr(user, 'profile', None)
        if not profile:
            return False
        
        # Check if has completed bookings
        completed_bookings = user.bookings.filter(status='completed').count()
        if completed_bookings == 0:
            return False
        
        return True
    
    @classmethod
    def get_verification_badge(cls, review):
        """Get verification badge based on checks"""
        badges = []
        
        if cls.verify_booking(review):
            badges.append('verified_booking')
        
        if cls.verify_purchase(review):
            badges.append('verified_purchase')
        
        if cls.verify_identity(review):
            badges.append('verified_identity')
        
        return badges
    
    @classmethod
    def verify_all(cls, review):
        """Run all verification checks"""
        return {
            'is_verified_booking': cls.verify_booking(review),
            'is_verified_purchase': cls.verify_purchase(review),
            'is_duplicate': cls.check_duplicate(review),
            'is_frequency_ok': not cls.check_frequency(review.user),
            'is_identity_verified': cls.verify_identity(review),
            'badges': cls.get_verification_badge(review)
        }

class ReviewValidator:
    """Validate review content"""
    
    MIN_LENGTH = 20
    MAX_LENGTH = 5000
    MIN_RATING = 1
    MAX_RATING = 5
    
    @classmethod
    def validate_length(cls, content):
        """Validate review length"""
        if len(content) < cls.MIN_LENGTH:
            return False, f"Review must be at least {cls.MIN_LENGTH} characters"
        if len(content) > cls.MAX_LENGTH:
            return False, f"Review cannot exceed {cls.MAX_LENGTH} characters"
        return True, None
    
    @classmethod
    def validate_rating(cls, rating):
        """Validate rating value"""
        try:
            rating = int(rating)
            if cls.MIN_RATING <= rating <= cls.MAX_RATING:
                return True, None
            return False, f"Rating must be between {cls.MIN_RATING} and {cls.MAX_RATING}"
        except (ValueError, TypeError):
            return False, "Invalid rating value"
    
    @classmethod
    def validate_title(cls, title):
        """Validate review title"""
        if not title:
            return False, "Title is required"
        if len(title) < 5:
            return False, "Title must be at least 5 characters"
        if len(title) > 100:
            return False, "Title cannot exceed 100 characters"
        return True, None
    
    @classmethod
    def validate_content(cls, content):
        """Validate review content"""
        if not content:
            return False, "Review content is required"
        
        # Check for excessive special characters
        special_chars = sum(not c.isalnum() and not c.isspace() for c in content)
        if special_chars / len(content) > 0.3:
            return False, "Too many special characters"
        
        return True, None

class TestimonialManager:
    """Manage testimonials for marketing"""
    
    @classmethod
    def select_featured(cls, limit=5):
        """Select featured testimonials"""
        # Prioritize high-rated, recent, verified reviews
        testimonials = Testimonial.objects.filter(
            is_verified=True
        ).order_by(
            '-is_featured',
            '-rating',
            '-created_at'
        )[:limit]
        
        return testimonials
    
    @classmethod
    def create_from_review(cls, review):
        """Create testimonial from review"""
        if review.overall_rating >= 4 and review.status == 'approved':
            testimonial, created = Testimonial.objects.get_or_create(
                review=review,
                defaults={
                    'user': review.user,
                    'customer_name': review.display_name,
                    'content': review.content,
                    'rating': review.overall_rating,
                    'is_verified': review.is_verified
                }
            )
            return testimonial
        return None
    
    @classmethod
    def rotate_testimonials(cls):
        """Rotate featured testimonials"""
        # Unfeature all
        Testimonial.objects.update(is_featured=False)
        
        # Select new featured
        featured = cls.select_featured()
        for testimonial in featured:
            testimonial.is_featured = True
            testimonial.save()
        
        return featured.count()