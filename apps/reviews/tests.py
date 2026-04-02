from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model
from .models import Review, Testimonial, ReviewVote
from apps.bookings.models import Booking
from apps.fleet.models import Aircraft, AircraftManufacturer

User = get_user_model()

class ReviewModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        
        manufacturer = AircraftManufacturer.objects.create(
            name='Boeing',
            country='USA'
        )
        
        self.aircraft = Aircraft.objects.create(
            registration_number='N12345',
            manufacturer=manufacturer,
            model='737-800',
            passenger_capacity=180,
            year_of_manufacture=2020,
            hourly_rate_usd=5000
        )
        
        self.booking = Booking.objects.create(
            user=self.user,
            aircraft=self.aircraft,
            departure_airport='JFK',
            arrival_airport='LAX',
            departure_datetime=timezone.now() + timezone.timedelta(days=1),
            arrival_datetime=timezone.now() + timezone.timedelta(days=1, hours=5),
            passenger_count=2,
            total_amount_usd=25000,
            status='completed'
        )
    
    def test_create_review(self):
        review = Review.objects.create(
            user=self.user,
            booking=self.booking,
            aircraft=self.aircraft,
            display_name='Test User',
            title='Great flight',
            content='Amazing experience!',
            overall_rating=5,
            status='pending'
        )
        
        self.assertEqual(review.review_number[:3], 'REV')
        self.assertEqual(review.overall_rating, 5)
        self.assertEqual(review.status, 'pending')
    
    def test_approve_review(self):
        review = Review.objects.create(
            user=self.user,
            booking=self.booking,
            aircraft=self.aircraft,
            display_name='Test User',
            title='Great flight',
            content='Amazing experience!',
            overall_rating=5,
            status='pending'
        )
        
        review.approve(self.user)
        
        self.assertEqual(review.status, 'approved')
        self.assertEqual(review.moderated_by, self.user)
        self.assertIsNotNone(review.moderated_at)
    
    def test_vote_review(self):
        review = Review.objects.create(
            user=self.user,
            booking=self.booking,
            aircraft=self.aircraft,
            display_name='Test User',
            title='Great flight',
            content='Amazing experience!',
            overall_rating=5,
            status='approved'
        )
        
        other_user = User.objects.create_user(
            email='other@example.com',
            password='testpass123'
        )
        
        vote = ReviewVote.objects.create(
            review=review,
            user=other_user,
            vote_type='helpful'
        )
        
        self.assertEqual(vote.vote_type, 'helpful')
        self.assertEqual(review.helpful_votes, 0)  # Not updated automatically
        
        review.vote_helpful()
        self.assertEqual(review.helpful_votes, 1)

class ReviewViewsTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.client.login(email='test@example.com', password='testpass123')
    
    def test_review_list_view(self):
        response = self.client.get(reverse('reviews:list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'reviews/list.html')
    
    def test_create_review_view(self):
        # Create test data
        manufacturer = AircraftManufacturer.objects.create(name='Boeing', country='USA')
        aircraft = Aircraft.objects.create(
            registration_number='N12345',
            manufacturer=manufacturer,
            model='737',
            passenger_capacity=100,
            year_of_manufacture=2020,
            hourly_rate_usd=5000
        )
        booking = Booking.objects.create(
            user=self.user,
            aircraft=aircraft,
            departure_airport='JFK',
            arrival_airport='LAX',
            departure_datetime=timezone.now() + timezone.timedelta(days=1),
            arrival_datetime=timezone.now() + timezone.timedelta(days=1, hours=5),
            passenger_count=2,
            total_amount_usd=25000,
            status='completed'
        )
        
        response = self.client.get(reverse('reviews:create', args=[booking.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'reviews/create.html')