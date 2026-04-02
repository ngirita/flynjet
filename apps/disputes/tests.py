from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model
from .models import Dispute, DisputeMessage, DisputeResolution
from apps.bookings.models import Booking
from apps.fleet.models import Aircraft, AircraftManufacturer

User = get_user_model()

class DisputeModelTest(TestCase):
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
            status='confirmed'
        )
    
    def test_create_dispute(self):
        dispute = Dispute.objects.create(
            user=self.user,
            booking=self.booking,
            dispute_type='cancellation',
            subject='Test Dispute',
            description='This is a test dispute',
            disputed_amount=5000
        )
        
        self.assertEqual(dispute.dispute_number[:3], 'DSP')
        self.assertEqual(dispute.status, 'pending')
        self.assertEqual(dispute.disputed_amount, 5000)
    
    def test_add_message(self):
        dispute = Dispute.objects.create(
            user=self.user,
            booking=self.booking,
            dispute_type='cancellation',
            subject='Test Dispute',
            description='This is a test dispute'
        )
        
        message = DisputeMessage.objects.create(
            dispute=dispute,
            sender=self.user,
            message='Test message'
        )
        
        self.assertEqual(message.message, 'Test message')
        self.assertFalse(message.is_read)
    
    def test_resolve_dispute(self):
        dispute = Dispute.objects.create(
            user=self.user,
            booking=self.booking,
            dispute_type='cancellation',
            subject='Test Dispute',
            description='This is a test dispute'
        )
        
        admin = User.objects.create_user(
            email='admin@example.com',
            password='adminpass123',
            is_staff=True
        )
        
        dispute.resolve(
            resolution='Resolved in customer favor',
            outcome='Full refund issued',
            resolved_by=admin,
            refund_amount=5000
        )
        
        self.assertEqual(dispute.status, 'resolved')
        self.assertEqual(dispute.refund_amount, 5000)
        self.assertTrue(dispute.refund_issued)

class DisputeViewsTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.client.login(email='test@example.com', password='testpass123')
    
    def test_dispute_list_view(self):
        response = self.client.get(reverse('disputes:list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'disputes/list.html')
    
    def test_create_dispute_view(self):
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
            total_amount_usd=25000
        )
        
        response = self.client.get(reverse('disputes:create', args=[booking.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'disputes/create.html')