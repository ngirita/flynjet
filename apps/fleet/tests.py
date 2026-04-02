from django.test import TestCase
from django.urls import reverse
from .models import Aircraft, AircraftCategory, AircraftManufacturer

class FleetModelTest(TestCase):
    def setUp(self):
        self.category = AircraftCategory.objects.create(
            name='Private Jets',
            slug='private-jets',
            category_type='private_jet',
            description='Luxury private jets'
        )
        
        self.manufacturer = AircraftManufacturer.objects.create(
            name='Bombardier',
            country='Canada'
        )
        
        self.aircraft = Aircraft.objects.create(
            registration_number='C-FJET',
            manufacturer=self.manufacturer,
            category=self.category,
            model='Global 6000',
            year_of_manufacture=2022,
            passenger_capacity=16,
            crew_required=2,
            max_range_nm=6000,
            cruise_speed_knots=500,
            fuel_capacity_l=20000,
            hourly_rate_usd=8000,
            status='available'
        )
    
    def test_aircraft_creation(self):
        self.assertEqual(self.aircraft.registration_number, 'C-FJET')
        self.assertEqual(self.aircraft.manufacturer.name, 'Bombardier')
        self.assertEqual(self.aircraft.category.name, 'Private Jets')
        self.assertTrue(self.aircraft.is_available)
    
    def test_category_creation(self):
        self.assertEqual(str(self.category), 'Private Jets')
    
    def test_manufacturer_creation(self):
        self.assertEqual(str(self.manufacturer), 'Bombardier')

class FleetViewsTest(TestCase):
    def setUp(self):
        self.category = AircraftCategory.objects.create(
            name='Private Jets',
            slug='private-jets',
            category_type='private_jet',
            description='Luxury private jets',
            is_active=True
        )
        
        self.manufacturer = AircraftManufacturer.objects.create(
            name='Bombardier',
            country='Canada',
            is_active=True
        )
    
    def test_aircraft_list_view(self):
        response = self.client.get(reverse('fleet:list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'fleet/aircraft_list.html')
    
    def test_category_list_view(self):
        response = self.client.get(reverse('fleet:categories'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'fleet/category_list.html')