from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model
from .models import FlightTrack, TrackingPosition, TrackingShare, FlightAlert
from apps.bookings.models import Booking
from apps.fleet.models import Aircraft, AircraftManufacturer

User = get_user_model()

class TrackingModelTest(TestCase):
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
        
        self.booking = Booking.objects.create(
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
            total_amount_usd=27500,
            status='confirmed'
        )
    
    def test_create_flight_track(self):
        track = FlightTrack.objects.create(
            booking=self.booking,
            flight_number='FJ12345',
            aircraft_registration='N12345',
            departure_time=self.booking.departure_datetime,
            arrival_time=self.booking.arrival_datetime,
            departure_airport='JFK',
            arrival_airport='LAX'
        )
        
        self.assertEqual(track.flight_number, 'FJ12345')
        self.assertEqual(track.aircraft_registration, 'N12345')
        self.assertTrue(track.is_tracking)
    
    def test_update_position(self):
        track = FlightTrack.objects.create(
            booking=self.booking,
            flight_number='FJ12345',
            aircraft_registration='N12345',
            departure_time=self.booking.departure_datetime,
            arrival_time=self.booking.arrival_datetime,
            departure_airport='JFK',
            arrival_airport='LAX'
        )
        
        track.update_position(
            latitude=40.7128,
            longitude=-74.0060,
            altitude=35000,
            heading=270,
            speed=450
        )
        
        self.assertEqual(track.latitude, 40.7128)
        self.assertEqual(track.longitude, -74.0060)
        self.assertEqual(track.altitude, 35000)
        
        # Check that position history was created
        self.assertEqual(track.position_history.count(), 1)
    
    def test_tracking_share(self):
        track = FlightTrack.objects.create(
            booking=self.booking,
            flight_number='FJ12345',
            aircraft_registration='N12345',
            departure_time=self.booking.departure_datetime,
            arrival_time=self.booking.arrival_datetime,
            departure_airport='JFK',
            arrival_airport='LAX'
        )
        
        share = TrackingShare.objects.create(
            track=track,
            created_by=self.user,
            expires_at=timezone.now() + timezone.timedelta(hours=24)
        )
        
        self.assertTrue(share.is_valid())
        self.assertEqual(share.views, 0)
        
        share.record_view()
        self.assertEqual(share.views, 1)

class TrackingViewsTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.client.login(email='test@example.com', password='testpass123')
    
    def test_tracking_dashboard_view(self):
        response = self.client.get(reverse('tracking:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'tracking/dashboard.html')
    
    def test_api_track_position(self):
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
        track = FlightTrack.objects.create(
            booking=booking,
            flight_number='FJ12345',
            aircraft_registration='N12345',
            departure_time=booking.departure_datetime,
            arrival_time=booking.arrival_datetime,
            departure_airport='JFK',
            arrival_airport='LAX'
        )
        
        response = self.client.post(
            reverse('tracking:api_update_position', args=[track.id]),
            {'lat': 40.7128, 'lng': -74.0060, 'alt': 35000},
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)