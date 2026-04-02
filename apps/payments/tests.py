from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone  # ← MISSING IMPORT
from .models import Payment, RefundRequest
from apps.bookings.models import Booking
from apps.fleet.models import Aircraft, AircraftManufacturer  # ← MISSING AircraftManufacturer

User = get_user_model()


class PaymentModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
    
    def test_create_payment(self):
        payment = Payment.objects.create(
            user=self.user,
            transaction_id='TXN123456',
            payment_method='visa',
            amount_usd=1000.00,
            currency='USD',
            status='completed'
        )
        
        self.assertEqual(payment.amount_usd, 1000.00)
        self.assertEqual(payment.status, 'completed')
        self.assertEqual(str(payment), f"Payment {payment.transaction_id} - 1000.0 USD")


class PaymentViewsTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.client.login(email='test@example.com', password='testpass123')
    
    def test_payment_list_view(self):
        response = self.client.get(reverse('payments:list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'payments/payment_list.html')
    
    def test_payment_create_view(self):
        # Create a booking first
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
        
        response = self.client.get(reverse('payments:create', args=[booking.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'payments/payment_form.html')