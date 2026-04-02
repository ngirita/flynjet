from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model
from .models import Booking, Invoice
from apps.fleet.models import Aircraft, AircraftManufacturer

User = get_user_model()

class BookingModelTest(TestCase):
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
            hourly_rate_usd=5000,
            status='available'
        )
    
    def test_create_booking(self):
        booking = Booking.objects.create(
            user=self.user,
            aircraft=self.aircraft,
            departure_airport='JFK',
            arrival_airport='LAX',
            departure_datetime=timezone.now() + timezone.timedelta(days=1),
            arrival_datetime=timezone.now() + timezone.timedelta(days=1, hours=5),
            passenger_count=2,
            flight_duration_hours=5,
            base_price_usd=25000,
            tax_amount_usd=2500,
            total_amount_usd=27500
        )
        
        self.assertEqual(booking.booking_reference[:2], 'FJ')
        self.assertEqual(booking.status, 'draft')
        self.assertEqual(booking.total_amount_usd, 27500)

class BookingViewsTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.client.login(email='test@example.com', password='testpass123')
    
    def test_booking_list_view(self):
        response = self.client.get(reverse('bookings:list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'bookings/booking_list.html')
    
    def test_booking_create_view(self):
        response = self.client.get(reverse('bookings:create'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'bookings/booking_form.html')