from rest_framework import serializers
from apps.accounts.models import User
from apps.bookings.models import Booking
from apps.fleet.models import Aircraft


class MobileUserSerializer(serializers.ModelSerializer):
    """Mobile-optimized user serializer"""
    
    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'phone_number', 'user_type']


class MobileBookingSerializer(serializers.ModelSerializer):
    """Mobile-optimized booking serializer"""
    aircraft_model = serializers.CharField(source='aircraft.model', read_only=True)
    aircraft_image = serializers.ImageField(source='aircraft.thumbnail', read_only=True)
    
    class Meta:
        model = Booking
        fields = [
            'id', 'booking_reference', 'departure_airport', 'arrival_airport',
            'departure_datetime', 'arrival_datetime', 'status', 'total_amount_usd',
            'aircraft_model', 'aircraft_image', 'can_cancel'
        ]


class MobileAircraftSerializer(serializers.ModelSerializer):
    """Mobile-optimized aircraft serializer"""
    
    class Meta:
        model = Aircraft
        fields = [
            'id', 'registration_number', 'model', 'manufacturer', 'category',
            'passenger_capacity', 'max_range_nm', 'hourly_rate_usd', 'thumbnail'
        ]