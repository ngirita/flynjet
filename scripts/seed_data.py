#!/usr/bin/env python
import os
import sys
import django
import random
from datetime import datetime, timedelta

# Setup Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'flynjet.settings')
django.setup()

from django.contrib.auth import get_user_model
from apps.fleet.models import AircraftCategory, AircraftManufacturer, Aircraft
from apps.core.models import FAQ, Testimonial
from apps.accounts.models import User

User = get_user_model()

def create_users():
    print("Creating users...")
    
    # Create admin
    if not User.objects.filter(email='info@flynjet.com').exists():
        admin = User.objects.create_superuser(
            email='info@flynjet.com',
            password='Admin123!@#',
            first_name='Admin',
            last_name='User',
            user_type='admin'
        )
        print(f"Created admin: {admin.email}")
    
    # Create regular users
    for i in range(10):
        email = f'user{i}@example.com'
        if not User.objects.filter(email=email).exists():
            user = User.objects.create_user(
                email=email,
                password='User123!@#',
                first_name=f'First{i}',
                last_name=f'Last{i}',
                phone_number=f'+1234567{str(i).zfill(4)}'
            )
            print(f"Created user: {user.email}")

def create_fleet():
    print("\nCreating fleet data...")
    
    # Create categories
    categories = [
        {'name': 'Light Jets', 'slug': 'light-jets', 'category_type': 'private_jet', 'description': 'Perfect for short trips, 4-6 passengers'},
        {'name': 'Midsize Jets', 'slug': 'midsize-jets', 'category_type': 'private_jet', 'description': 'Ideal for medium range, 6-8 passengers'},
        {'name': 'Heavy Jets', 'slug': 'heavy-jets', 'category_type': 'private_jet', 'description': 'Long range luxury, 10-16 passengers'},
        {'name': 'Cargo Planes', 'slug': 'cargo', 'category_type': 'cargo', 'description': 'Freight and cargo transportation'},
        {'name': 'Helicopters', 'slug': 'helicopters', 'category_type': 'helicopter', 'description': 'Short distance urban travel'},
    ]
    
    for cat_data in categories:
        category, created = AircraftCategory.objects.get_or_create(
            slug=cat_data['slug'],
            defaults=cat_data
        )
        if created:
            print(f"Created category: {category.name}")
    
    # Create manufacturers
    manufacturers = [
        {'name': 'Bombardier', 'country': 'Canada'},
        {'name': 'Gulfstream', 'country': 'USA'},
        {'name': 'Cessna', 'country': 'USA'},
        {'name': 'Boeing', 'country': 'USA'},
        {'name': 'Airbus', 'country': 'France'},
        {'name': 'Embraer', 'country': 'Brazil'},
    ]
    
    for man_data in manufacturers:
        manufacturer, created = AircraftManufacturer.objects.get_or_create(
            name=man_data['name'],
            defaults=man_data
        )
        if created:
            print(f"Created manufacturer: {manufacturer.name}")
    
    # Create aircraft
    aircraft_data = [
        {
            'manufacturer': 'Bombardier',
            'model': 'Global 6000',
            'category': 'heavy-jets',
            'passenger_capacity': 16,
            'max_range_nm': 6000,
            'hourly_rate_usd': 8000,
            'year': 2022,
        },
        {
            'manufacturer': 'Gulfstream',
            'model': 'G650ER',
            'category': 'heavy-jets',
            'passenger_capacity': 14,
            'max_range_nm': 7500,
            'hourly_rate_usd': 9000,
            'year': 2023,
        },
        {
            'manufacturer': 'Cessna',
            'model': 'Citation XLS',
            'category': 'light-jets',
            'passenger_capacity': 8,
            'max_range_nm': 1800,
            'hourly_rate_usd': 3500,
            'year': 2021,
        },
        {
            'manufacturer': 'Embraer',
            'model': 'Phenom 300',
            'category': 'light-jets',
            'passenger_capacity': 8,
            'max_range_nm': 2000,
            'hourly_rate_usd': 3800,
            'year': 2022,
        },
    ]
    
    for data in aircraft_data:
        manufacturer = AircraftManufacturer.objects.get(name=data['manufacturer'])
        category = AircraftCategory.objects.get(slug=data['category'])
        
        reg_number = f"N{random.randint(100, 999)}{random.choice('ABCDEFGHJKLMNPQRSTUVWXYZ')}{random.randint(10,99)}"
        
        aircraft, created = Aircraft.objects.get_or_create(
            registration_number=reg_number,
            defaults={
                'manufacturer': manufacturer,
                'category': category,
                'model': data['model'],
                'year_of_manufacture': data['year'],
                'passenger_capacity': data['passenger_capacity'],
                'crew_required': 2,
                'baggage_capacity_kg': 500,
                'max_range_nm': data['max_range_nm'],
                'max_range_km': int(data['max_range_nm'] * 1.852),
                'cruise_speed_knots': 450,
                'max_speed_knots': 500,
                'service_ceiling_ft': 45000,
                'takeoff_distance_m': 1500,
                'landing_distance_m': 1200,
                'fuel_type': 'jet_a',
                'fuel_capacity_l': 8000,
                'fuel_consumption_lph': 800,
                'length_m': 20,
                'wingspan_m': 25,
                'height_m': 7,
                'cabin_length_m': 10,
                'cabin_width_m': 2.5,
                'cabin_height_m': 2,
                'max_takeoff_weight_kg': 20000,
                'max_landing_weight_kg': 18000,
                'empty_weight_kg': 12000,
                'payload_kg': 8000,
                'engine_type': 'Turbofan',
                'engine_count': 2,
                'avionics_suite': 'Rockwell Collins Pro Line Fusion',
                'wifi_available': True,
                'entertainment_system': True,
                'galley': True,
                'lavatory': True,
                'hourly_rate_usd': data['hourly_rate_usd'],
                'base_airport': 'TEB',
                'current_location': 'TEB',
                'status': 'available',
                'is_active': True,
            }
        )
        if created:
            print(f"Created aircraft: {aircraft.registration_number} - {aircraft.manufacturer.name} {aircraft.model}")

def create_faqs():
    print("\nCreating FAQs...")
    
    faqs = [
        {
            'question': 'How do I book a private jet?',
            'answer': 'You can book a private jet through our website by selecting your preferred aircraft, dates, and destinations. Our booking process is simple and secure.',
            'category': 'booking',
        },
        {
            'question': 'What payment methods do you accept?',
            'answer': 'We accept all major credit cards (Visa, MasterCard, American Express), bank transfers, and cryptocurrencies including USDT (ERC-20 and TRC-20), Bitcoin, and Ethereum.',
            'category': 'payment',
        },
        {
            'question': 'What is your cancellation policy?',
            'answer': 'Cancellations made 48 hours or more before departure receive a full refund. Cancellations within 48 hours are subject to a 50% cancellation fee.',
            'category': 'cancellation',
        },
        {
            'question': 'Are pets allowed on board?',
            'answer': 'Yes, pets are welcome on most of our aircraft. Please inform us in advance so we can make appropriate arrangements.',
            'category': 'general',
        },
        {
            'question': 'How far in advance should I book?',
            'answer': 'We recommend booking at least 48 hours in advance for guaranteed availability, but we can accommodate last-minute requests when aircraft are available.',
            'category': 'booking',
        },
    ]
    
    for faq_data in faqs:
        faq, created = FAQ.objects.get_or_create(
            question=faq_data['question'],
            defaults=faq_data
        )
        if created:
            print(f"Created FAQ: {faq.question[:50]}...")

def create_testimonials():
    print("\nCreating testimonials...")
    
    testimonials = [
        {
            'customer_name': 'John Smith',
            'customer_title': 'CEO',
            'customer_company': 'Tech Innovations Inc.',
            'content': 'Outstanding service! The aircraft was immaculate and the crew was professional. Will definitely use FlynJet again.',
            'rating': 5,
        },
        {
            'customer_name': 'Sarah Johnson',
            'customer_title': 'Managing Director',
            'customer_company': 'Global Investments',
            'content': 'FlynJet made our corporate travel seamless. The booking process was easy and the flight was perfect.',
            'rating': 5,
        },
        {
            'customer_name': 'Michael Chen',
            'customer_title': 'Entrepreneur',
            'customer_company': 'Chen Holdings',
            'content': 'Great experience from start to finish. The real-time tracking feature is excellent for coordinating ground transportation.',
            'rating': 5,
        },
    ]
    
    for test_data in testimonials:
        testimonial, created = Testimonial.objects.get_or_create(
            customer_name=test_data['customer_name'],
            defaults=test_data
        )
        if created:
            print(f"Created testimonial from: {testimonial.customer_name}")

def main():
    print("Starting database seeding...\n")
    create_users()
    create_fleet()
    create_faqs()
    create_testimonials()
    print("\nDatabase seeding completed!")

if __name__ == '__main__':
    main()