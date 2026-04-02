from rest_framework import serializers
from .models import (
    Aircraft, AircraftCategory, AircraftManufacturer,
    AircraftImage, AircraftSpecification, AircraftAvailability,
    AircraftMaintenance, AircraftDocument, FleetStats
)
from apps.bookings.models import Booking

# ===== IMAGE & SPECIFICATION SERIALIZERS (MOVE THESE UP) =====

class AircraftImageSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()
    
    class Meta:
        model = AircraftImage
        fields = ['id', 'image', 'image_url', 'thumbnail', 'thumbnail_url', 'caption', 'is_primary', 'sort_order']
    
    def get_image_url(self, obj):
        if obj.image:
            return obj.image.url
        return None
    
    def get_thumbnail_url(self, obj):
        if obj.thumbnail:
            return obj.thumbnail.url
        return None


class AircraftSpecificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = AircraftSpecification
        fields = '__all__'


# ===== CATEGORY & MANUFACTURER SERIALIZERS =====

class AircraftCategorySerializer(serializers.ModelSerializer):
    aircraft_count = serializers.SerializerMethodField()
    
    class Meta:
        model = AircraftCategory
        fields = '__all__'
    
    def get_aircraft_count(self, obj):
        return obj.aircraft.filter(is_active=True).count()


class AircraftManufacturerSerializer(serializers.ModelSerializer):
    aircraft_count = serializers.SerializerMethodField()
    
    class Meta:
        model = AircraftManufacturer
        fields = '__all__'
    
    def get_aircraft_count(self, obj):
        return obj.aircraft.filter(is_active=True).count()


# ===== AIRCRAFT SERIALIZERS =====

class AircraftSerializer(serializers.ModelSerializer):
    """Basic Aircraft serializer for use in other apps"""
    manufacturer_name = serializers.CharField(source='manufacturer.name', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    
    class Meta:
        model = Aircraft
        fields = [
            'id', 'registration_number', 'manufacturer', 'manufacturer_name',
            'model', 'variant', 'category', 'category_name',
            'year_of_manufacture', 'passenger_capacity', 'crew_required',
            'cargo_capacity_kg', 'baggage_capacity_kg',
            'max_range_nm', 'max_range_km', 'cruise_speed_knots',
            'max_speed_knots', 'service_ceiling_ft',
            'fuel_type', 'fuel_capacity_l', 'fuel_consumption_lph',
            'wifi_available', 'satellite_phone', 'entertainment_system',
            'galley', 'lavatory', 'shower', 'bedroom', 'conference_table',
            'thumbnail', 'status', 'base_airport', 'current_location',
            'hourly_rate_usd', 'daily_rate_usd', 'weekly_rate_usd',
            'monthly_rate_usd', 'minimum_booking_hours',
            'is_active', 'is_featured'
        ]
        read_only_fields = ['id']


class AircraftListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for aircraft lists"""
    manufacturer_name = serializers.CharField(source='manufacturer.name')
    category_name = serializers.CharField(source='category.name')
    
    class Meta:
        model = Aircraft
        fields = [
            'id', 'registration_number', 'manufacturer_name', 'model',
            'category_name', 'thumbnail', 'passenger_capacity',
            'max_range_nm', 'hourly_rate_usd', 'status', 'is_featured'
        ]


class AircraftDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for single aircraft view"""
    manufacturer = serializers.SerializerMethodField()
    category = serializers.SerializerMethodField()
    images = AircraftImageSerializer(many=True, read_only=True)  # Now this is defined
    specifications = AircraftSpecificationSerializer(many=True, read_only=True)  # Now this is defined
    next_available_date = serializers.SerializerMethodField()
    total_flight_hours_display = serializers.SerializerMethodField()
    
    class Meta:
        model = Aircraft
        fields = '__all__'
    
    def get_manufacturer(self, obj):
        return {
            'id': obj.manufacturer.id,
            'name': obj.manufacturer.name,
            'logo': obj.manufacturer.logo.url if obj.manufacturer.logo else None,
            'country': obj.manufacturer.country
        }
    
    def get_category(self, obj):
        return {
            'id': obj.category.id,
            'name': obj.category.name,
            'slug': obj.category.slug,
            'icon': obj.category.icon.url if obj.category.icon else None
        }
    
    def get_next_available_date(self, obj):
        # Find next available date
        from django.utils import timezone
        from datetime import timedelta
        
        if obj.status == 'available':
            return timezone.now().date().isoformat()
        
        # Check future bookings
        last_booking = Booking.objects.filter(
            aircraft=obj,
            status__in=['confirmed', 'paid'],
            departure_datetime__gte=timezone.now()
        ).order_by('-arrival_datetime').first()
        
        if last_booking:
            return (last_booking.arrival_datetime + timedelta(days=1)).date().isoformat()
        
        return None
    
    def get_total_flight_hours_display(self, obj):
        hours = obj.total_flight_hours
        years = int(hours // 8760)
        months = int((hours % 8760) // 730)
        
        if years > 0:
            return f"{years}y {months}m"
        elif months > 0:
            return f"{months}m"
        else:
            return f"{int(hours)}h"


# ===== AVAILABILITY SERIALIZERS =====

class AircraftAvailabilitySerializer(serializers.ModelSerializer):
    aircraft_registration = serializers.CharField(source='aircraft.registration_number', read_only=True)
    
    class Meta:
        model = AircraftAvailability
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


class AircraftAvailabilityCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = AircraftAvailability
        fields = ['aircraft', 'start_datetime', 'end_datetime', 'is_available', 'reason']
    
    def validate(self, data):
        if data['start_datetime'] >= data['end_datetime']:
            raise serializers.ValidationError("End time must be after start time")
        
        # Check for overlapping availability blocks
        from django.db.models import Q
        overlapping = AircraftAvailability.objects.filter(
            aircraft=data['aircraft'],
            start_datetime__lt=data['end_datetime'],
            end_datetime__gt=data['start_datetime']
        )
        
        if overlapping.exists():
            raise serializers.ValidationError("This time slot overlaps with an existing availability block")
        
        return data


# ===== MAINTENANCE SERIALIZERS =====

class AircraftMaintenanceSerializer(serializers.ModelSerializer):
    aircraft_registration = serializers.CharField(source='aircraft.registration_number', read_only=True)
    aircraft_model = serializers.CharField(source='aircraft.model', read_only=True)
    technician_name_display = serializers.SerializerMethodField()
    duration_display = serializers.SerializerMethodField()
    
    class Meta:
        model = AircraftMaintenance
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at', 'completed_at']
    
    def get_technician_name_display(self, obj):
        if obj.technician_name:
            return obj.technician_name
        return "Not assigned"
    
    def get_duration_display(self, obj):
        if obj.actual_start and obj.actual_end:
            duration = obj.actual_end - obj.actual_start
            days = duration.days
            hours = duration.seconds // 3600
            if days > 0:
                return f"{days}d {hours}h"
            return f"{hours}h"
        return "In progress"


class AircraftMaintenanceCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = AircraftMaintenance
        fields = [
            'aircraft', 'maintenance_type', 'title', 'description',
            'scheduled_start', 'scheduled_end', 'maintenance_location',
            'maintenance_facility', 'estimated_cost_usd', 'parts_used'
        ]
    
    def validate(self, data):
        if data['scheduled_start'] >= data['scheduled_end']:
            raise serializers.ValidationError("End time must be after start time")
        
        # Check if aircraft is available
        if data['aircraft'].status == 'maintenance':
            raise serializers.ValidationError("Aircraft is already in maintenance")
        
        return data


class AircraftMaintenanceDetailSerializer(serializers.ModelSerializer):
    aircraft_details = AircraftSerializer(source='aircraft', read_only=True)
    created_by_details = serializers.SerializerMethodField()
    
    class Meta:
        model = AircraftMaintenance
        fields = '__all__'
    
    def get_created_by_details(self, obj):
        if obj.created_by:
            return {
                'id': obj.created_by.id,
                'name': obj.created_by.get_full_name(),
                'email': obj.created_by.email
            }
        return None


# ===== DOCUMENT SERIALIZERS =====

class AircraftDocumentSerializer(serializers.ModelSerializer):
    aircraft_registration = serializers.CharField(source='aircraft.registration_number', read_only=True)
    is_expired = serializers.BooleanField(read_only=True)
    days_until_expiry = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = AircraftDocument
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at', 'approved_at']


class AircraftDocumentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = AircraftDocument
        fields = [
            'aircraft', 'document_type', 'title', 'document_number',
            'file', 'issue_date', 'expiry_date', 'issuing_authority', 'notes'
        ]


# ===== STATISTICS SERIALIZERS =====

class FleetStatsSerializer(serializers.ModelSerializer):
    class Meta:
        model = FleetStats
        fields = '__all__'


class FleetStatsDetailSerializer(serializers.ModelSerializer):
    utilization_rate_display = serializers.SerializerMethodField()
    
    class Meta:
        model = FleetStats
        fields = '__all__'
    
    def get_utilization_rate_display(self, obj):
        return f"{obj.average_utilization_rate}%"


class FleetDashboardSerializer(serializers.Serializer):
    """Serializer for fleet dashboard data"""
    total_aircraft = serializers.IntegerField()
    available = serializers.IntegerField()
    in_maintenance = serializers.IntegerField()
    booked = serializers.IntegerField()
    available_percentage = serializers.FloatField()
    upcoming_maintenance = serializers.ListField(child=serializers.DictField())
    expiring_documents = serializers.ListField(child=serializers.DictField())
    recent_activity = serializers.ListField(child=serializers.DictField())


# ===== SIMPLE SERIALIZERS FOR API RESPONSES =====

class SimpleAircraftSerializer(serializers.ModelSerializer):
    """Extremely simple serializer for dropdowns and selects"""
    display_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Aircraft
        fields = ['id', 'registration_number', 'model', 'display_name']
    
    def get_display_name(self, obj):
        return f"{obj.manufacturer.name} {obj.model} - {obj.registration_number}"


class SimpleCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = AircraftCategory
        fields = ['id', 'name', 'slug']


class SimpleManufacturerSerializer(serializers.ModelSerializer):
    class Meta:
        model = AircraftManufacturer
        fields = ['id', 'name', 'logo']