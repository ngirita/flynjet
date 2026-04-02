import uuid
from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.core.models import TimeStampedModel
from apps.accounts.models import User
from apps.bookings.models import Booking
from apps.fleet.models import Aircraft

class Review(TimeStampedModel):
    """Customer reviews for flights and services"""
    
    REVIEW_TYPES = (
        ('flight', 'Flight Review'),
        ('aircraft', 'Aircraft Review'),
        ('service', 'Service Review'),
        ('agent', 'Agent Review'),
    )
    
    REVIEW_STATUS = (
        ('pending', 'Pending Moderation'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('flagged', 'Flagged'),
        ('featured', 'Featured'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    review_number = models.CharField(max_length=50, unique=True, db_index=True)
    
    # Reviewer
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews')
    display_name = models.CharField(max_length=200)
    is_verified = models.BooleanField(default=False)
    
    # Related Objects
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, null=True, blank=True, related_name='reviews')
    aircraft = models.ForeignKey(Aircraft, on_delete=models.CASCADE, null=True, blank=True, related_name='reviews')
    agent = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='agent_reviews')
    
    # Review Content
    review_type = models.CharField(max_length=20, choices=REVIEW_TYPES)
    title = models.CharField(max_length=200)
    content = models.TextField()
    
    # Ratings (1-5)
    overall_rating = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    punctuality_rating = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)], null=True, blank=True)
    comfort_rating = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)], null=True, blank=True)
    service_rating = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)], null=True, blank=True)
    value_rating = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)], null=True, blank=True)
    cleanliness_rating = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)], null=True, blank=True)
    
    # Media
    photos = models.JSONField(default=list, blank=True)
    videos = models.JSONField(default=list, blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=REVIEW_STATUS, default='pending')
    moderation_note = models.TextField(blank=True)
    moderated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='moderated_reviews')
    moderated_at = models.DateTimeField(null=True, blank=True)
    
    # Helpfulness
    helpful_votes = models.IntegerField(default=0)
    not_helpful_votes = models.IntegerField(default=0)
    report_count = models.IntegerField(default=0)
    
    # Response
    response = models.TextField(blank=True)
    responded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='review_responses')
    responded_at = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['review_number']),
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['aircraft', 'status']),
            models.Index(fields=['booking']),
            models.Index(fields=['status', 'overall_rating']),
        ]
    
    def __str__(self):
        return f"Review {self.review_number} by {self.display_name}"
    
    def save(self, *args, **kwargs):
        if not self.review_number:
            self.review_number = self.generate_review_number()
        super().save(*args, **kwargs)
    
    def generate_review_number(self):
        import random
        import string
        timestamp = timezone.now().strftime('%Y%m')
        random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        return f"REV{timestamp}{random_str}"
    
    def approve(self, moderator):
        """Approve review"""
        self.status = 'approved'
        self.moderated_by = moderator
        self.moderated_at = timezone.now()
        self.save(update_fields=['status', 'moderated_by', 'moderated_at'])
        
        # Update aircraft rating
        if self.aircraft:
            self.update_aircraft_rating()
    
    def reject(self, moderator, reason):
        """Reject review"""
        self.status = 'rejected'
        self.moderation_note = reason
        self.moderated_by = moderator
        self.moderated_at = timezone.now()
        self.save(update_fields=['status', 'moderation_note', 'moderated_by', 'moderated_at'])
    
    def feature(self):
        """Feature this review"""
        self.status = 'featured'
        self.save(update_fields=['status'])
    
    def add_response(self, response, responder):
        """Add management response to review"""
        self.response = response
        self.responded_by = responder
        self.responded_at = timezone.now()
        self.save(update_fields=['response', 'responded_by', 'responded_at'])
    
    def vote_helpful(self):
        """Increment helpful votes"""
        self.helpful_votes += 1
        self.save(update_fields=['helpful_votes'])
    
    def vote_not_helpful(self):
        """Increment not helpful votes"""
        self.not_helpful_votes += 1
        self.save(update_fields=['not_helpful_votes'])
    
    def report(self):
        """Report review as inappropriate"""
        self.report_count += 1
        self.save(update_fields=['report_count'])
        
        # Auto-flag if reported multiple times
        if self.report_count >= 3:
            self.status = 'flagged'
            self.save(update_fields=['status'])
    
    def update_aircraft_rating(self):
        """Update aircraft's average rating"""
        if not self.aircraft:
            return
        
        reviews = Review.objects.filter(
            aircraft=self.aircraft,
            status__in=['approved', 'featured']
        )
        
        avg_rating = reviews.aggregate(models.Avg('overall_rating'))['overall_rating__avg']
        review_count = reviews.count()
        
        self.aircraft.average_rating = avg_rating or 0
        self.aircraft.review_count = review_count
        self.aircraft.save(update_fields=['average_rating', 'review_count'])


class ReviewVote(models.Model):
    """Votes on review helpfulness"""
    
    VOTE_TYPES = (
        ('helpful', 'Helpful'),
        ('not_helpful', 'Not Helpful'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    review = models.ForeignKey(Review, on_delete=models.CASCADE, related_name='votes')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='review_votes')
    vote_type = models.CharField(max_length=20, choices=VOTE_TYPES)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['review', 'user']
    
    def __str__(self):
        return f"{self.user.email} voted {self.vote_type} on {self.review.review_number}"


class ReviewPhoto(models.Model):
    """Photos attached to reviews"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    review = models.ForeignKey(Review, on_delete=models.CASCADE, related_name='review_photos')
    
    image = models.ImageField(upload_to='review_photos/%Y/%m/%d/')
    caption = models.CharField(max_length=200, blank=True)
    
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['uploaded_at']
    
    def __str__(self):
        return f"Photo for {self.review.review_number}"


class Testimonial(TimeStampedModel):
    """Featured testimonials for marketing"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    testimonial_number = models.CharField(max_length=50, unique=True)
    
    # Source
    review = models.ForeignKey(Review, on_delete=models.SET_NULL, null=True, blank=True, related_name='testimonials')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviews_testimonials')
    
    # Content
    customer_name = models.CharField(max_length=200)
    customer_title = models.CharField(max_length=200, blank=True)
    customer_company = models.CharField(max_length=200, blank=True)
    customer_image = models.ImageField(upload_to='testimonials/', blank=True)
    
    content = models.TextField()
    rating = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    
    # Display Options
    is_featured = models.BooleanField(default=False)
    display_order = models.IntegerField(default=0)
    
    # Verification
    is_verified = models.BooleanField(default=False)
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='verified_reviews_testimonials')
    
    class Meta:
        ordering = ['display_order', '-created_at']
        indexes = [
            models.Index(fields=['testimonial_number']),
            models.Index(fields=['is_featured']),
        ]
    
    def __str__(self):
        return f"Testimonial by {self.customer_name}"
    
    def save(self, *args, **kwargs):
        if not self.testimonial_number:
            self.testimonial_number = self.generate_testimonial_number()
        super().save(*args, **kwargs)
    
    def generate_testimonial_number(self):
        import random
        import string
        timestamp = timezone.now().strftime('%Y%m')
        random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        return f"TEST{timestamp}{random_str}"
    
    def verify(self, verifier):
        """Verify testimonial"""
        self.is_verified = True
        self.verified_at = timezone.now()
        self.verified_by = verifier
        self.save(update_fields=['is_verified', 'verified_at', 'verified_by'])

class ReviewSummary(models.Model):
    """Aggregated review statistics"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Target
    aircraft = models.ForeignKey(Aircraft, on_delete=models.CASCADE, null=True, blank=True, related_name='review_summaries')
    agent = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='review_summaries')
    
    # Statistics
    total_reviews = models.IntegerField(default=0)
    average_rating = models.FloatField(default=0.0)
    
    # Rating Distribution
    rating_5_count = models.IntegerField(default=0)
    rating_4_count = models.IntegerField(default=0)
    rating_3_count = models.IntegerField(default=0)
    rating_2_count = models.IntegerField(default=0)
    rating_1_count = models.IntegerField(default=0)
    
    # Period
    period_start = models.DateField()
    period_end = models.DateField()
    
    calculated_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['aircraft', 'period_start', 'period_end']
        indexes = [
            models.Index(fields=['aircraft', '-period_end']),
        ]
    
    def __str__(self):
        target = self.aircraft or self.agent
        return f"Review Summary for {target} ({self.period_start} to {self.period_end})"
    
    @classmethod
    def calculate_for_aircraft(cls, aircraft, start_date, end_date):
        """Calculate review summary for an aircraft"""
        reviews = Review.objects.filter(
            aircraft=aircraft,
            created_at__date__gte=start_date,
            created_at__date__lte=end_date,
            status__in=['approved', 'featured']
        )
        
        summary = cls.objects.create(
            aircraft=aircraft,
            period_start=start_date,
            period_end=end_date,
            total_reviews=reviews.count(),
            average_rating=reviews.aggregate(models.Avg('overall_rating'))['overall_rating__avg'] or 0,
            rating_5_count=reviews.filter(overall_rating=5).count(),
            rating_4_count=reviews.filter(overall_rating=4).count(),
            rating_3_count=reviews.filter(overall_rating=3).count(),
            rating_2_count=reviews.filter(overall_rating=2).count(),
            rating_1_count=reviews.filter(overall_rating=1).count(),
        )
        
        return summary