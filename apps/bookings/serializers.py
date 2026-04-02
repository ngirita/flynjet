from rest_framework import serializers
from .models import Booking, BookingPassenger, BookingAddon, Invoice, InvoiceItem
from apps.fleet.serializers import AircraftSerializer, AircraftDetailSerializer
from apps.accounts.serializers import UserSerializer
from apps.airports.models import Airport  # Add this import

class BookingPassengerSerializer(serializers.ModelSerializer):
    class Meta:
        model = BookingPassenger
        fields = '__all__'


class BookingAddonSerializer(serializers.ModelSerializer):
    class Meta:
        model = BookingAddon
        fields = '__all__'


class BookingSerializer(serializers.ModelSerializer):
    passengers = BookingPassengerSerializer(many=True, read_only=True)
    addons = BookingAddonSerializer(many=True, read_only=True)
    aircraft_details = AircraftSerializer(source='aircraft', read_only=True)
    
    # Add airport details
    departure_airport_details = serializers.SerializerMethodField()
    arrival_airport_details = serializers.SerializerMethodField()
    
    class Meta:
        model = Booking
        fields = '__all__'
        read_only_fields = [
            'booking_reference', 'status', 'payment_status',
            'total_amount_usd', 'amount_paid', 'amount_due',
            'created_at', 'updated_at'
        ]
    
    def get_departure_airport_details(self, obj):
        """Get departure airport details if available"""
        if obj.departure_airport:
            try:
                airport = Airport.objects.get(iata_code=obj.departure_airport)
                return {
                    'iata_code': airport.iata_code,
                    'name': airport.name,
                    'city': airport.city,
                    'country': airport.country,
                    'country_code': airport.country_code,
                    'timezone': airport.timezone
                }
            except Airport.DoesNotExist:
                return {
                    'iata_code': obj.departure_airport,
                    'name': None,
                    'city': None,
                    'country': None
                }
        return None
    
    def get_arrival_airport_details(self, obj):
        """Get arrival airport details if available"""
        if obj.arrival_airport:
            try:
                airport = Airport.objects.get(iata_code=obj.arrival_airport)
                return {
                    'iata_code': airport.iata_code,
                    'name': airport.name,
                    'city': airport.city,
                    'country': airport.country,
                    'country_code': airport.country_code,
                    'timezone': airport.timezone
                }
            except Airport.DoesNotExist:
                return {
                    'iata_code': obj.arrival_airport,
                    'name': None,
                    'city': None,
                    'country': None
                }
        return None


class BookingCreateSerializer(serializers.ModelSerializer):
    passengers = BookingPassengerSerializer(many=True)
    
    class Meta:
        model = Booking
        fields = [
            'aircraft', 'flight_type', 'departure_airport',
            'arrival_airport', 'departure_datetime', 'arrival_datetime',
            'passenger_count', 'passengers', 'special_requests',
            'dietary_requirements', 'medical_requirements'
        ]
    
    def validate_departure_airport(self, value):
        """Validate that airport exists in database"""
        if value:
            try:
                Airport.objects.get(iata_code=value)
            except Airport.DoesNotExist:
                raise serializers.ValidationError(
                    f"Airport with IATA code '{value}' not found. Please use a valid IATA code."
                )
        return value
    
    def validate_arrival_airport(self, value):
        """Validate that airport exists in database"""
        if value:
            try:
                Airport.objects.get(iata_code=value)
            except Airport.DoesNotExist:
                raise serializers.ValidationError(
                    f"Airport with IATA code '{value}' not found. Please use a valid IATA code."
                )
        return value
    
    def validate(self, data):
        """Validate that departure and arrival airports are different"""
        if data.get('departure_airport') == data.get('arrival_airport'):
            raise serializers.ValidationError(
                "Departure and arrival airports must be different."
            )
        return data
    
    def create(self, validated_data):
        passengers_data = validated_data.pop('passengers')
        validated_data['user'] = self.context['request'].user
        validated_data['status'] = 'draft'
        
        booking = Booking.objects.create(**validated_data)
        
        for passenger_data in passengers_data:
            BookingPassenger.objects.create(booking=booking, **passenger_data)
        
        booking.calculate_totals()
        booking.save()
        
        return booking


class BookingDetailSerializer(serializers.ModelSerializer):
    """Detailed Booking serializer with all related fields"""
    passengers = BookingPassengerSerializer(many=True, read_only=True)
    addons = BookingAddonSerializer(many=True, read_only=True)
    aircraft = AircraftDetailSerializer(read_only=True)
    user = UserSerializer(read_only=True)
    
    # Add airport details
    departure_airport_details = serializers.SerializerMethodField()
    arrival_airport_details = serializers.SerializerMethodField()
    
    passenger_count_display = serializers.SerializerMethodField()
    duration_display = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    payment_status_display = serializers.CharField(source='get_payment_status_display', read_only=True)
    flight_type_display = serializers.CharField(source='get_flight_type_display', read_only=True)
    
    class Meta:
        model = Booking
        fields = '__all__'
        read_only_fields = [
            'id', 'booking_reference', 'created_at', 'updated_at',
            'confirmed_at', 'completed_at', 'cancelled_at'
        ]
    
    def get_departure_airport_details(self, obj):
        """Get departure airport details if available"""
        if obj.departure_airport:
            try:
                airport = Airport.objects.get(iata_code=obj.departure_airport)
                return {
                    'iata_code': airport.iata_code,
                    'icao_code': airport.icao_code,
                    'name': airport.name,
                    'city': airport.city,
                    'country': airport.country,
                    'country_code': airport.country_code,
                    'timezone': airport.timezone,
                    'latitude': airport.latitude,
                    'longitude': airport.longitude,
                }
            except Airport.DoesNotExist:
                return {
                    'iata_code': obj.departure_airport,
                    'name': None,
                    'city': None,
                    'country': None
                }
        return None
    
    def get_arrival_airport_details(self, obj):
        """Get arrival airport details if available"""
        if obj.arrival_airport:
            try:
                airport = Airport.objects.get(iata_code=obj.arrival_airport)
                return {
                    'iata_code': airport.iata_code,
                    'icao_code': airport.icao_code,
                    'name': airport.name,
                    'city': airport.city,
                    'country': airport.country,
                    'country_code': airport.country_code,
                    'timezone': airport.timezone,
                    'latitude': airport.latitude,
                    'longitude': airport.longitude,
                }
            except Airport.DoesNotExist:
                return {
                    'iata_code': obj.arrival_airport,
                    'name': None,
                    'city': None,
                    'country': None
                }
        return None
    
    def get_passenger_count_display(self, obj):
        return f"{obj.passenger_count} passenger{'s' if obj.passenger_count > 1 else ''}"
    
    def get_duration_display(self, obj):
        if obj.departure_datetime and obj.arrival_datetime:
            duration = obj.arrival_datetime - obj.departure_datetime
            hours = duration.seconds // 3600
            minutes = (duration.seconds % 3600) // 60
            return f"{hours}h {minutes}m"
        return "N/A"


class InvoiceItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceItem
        fields = '__all__'


class InvoiceSerializer(serializers.ModelSerializer):
    items = InvoiceItemSerializer(many=True, read_only=True)
    booking_details = BookingSerializer(source='booking', read_only=True)
    
    # Add airport details to invoice
    route_display = serializers.SerializerMethodField()
    
    class Meta:
        model = Invoice
        fields = '__all__'
        read_only_fields = ['invoice_number', 'verification_hash']
    
    def get_route_display(self, obj):
        """Get formatted route display for invoice"""
        if obj.booking:
            dep = obj.booking.departure_airport
            arr = obj.booking.arrival_airport
            
            dep_name = dep
            arr_name = arr
            
            try:
                dep_airport = Airport.objects.get(iata_code=dep)
                dep_name = f"{dep_airport.city} ({dep})"
            except Airport.DoesNotExist:
                pass
            
            try:
                arr_airport = Airport.objects.get(iata_code=arr)
                arr_name = f"{arr_airport.city} ({arr})"
            except Airport.DoesNotExist:
                pass
            
            return f"{dep_name} → {arr_name}"
        return "N/A"
    
    def to_representation(self, instance):
        """Debug and safely handle both model instances and dictionaries"""
        print("\n" + "=" * 80)
        print("DEBUG: InvoiceSerializer.to_representation called")
        print(f"Instance type: {type(instance)}")
        
        # If instance is a dictionary, try to get it from database
        if isinstance(instance, dict):
            print("WARNING: Instance is a DICTIONARY!")
            print(f"Keys: {list(instance.keys())}")
            
            # Try to get the actual model instance from the ID
            if 'id' in instance and instance['id']:
                try:
                    from .models import Invoice
                    instance = Invoice.objects.get(id=instance['id'])
                    print(f"Retrieved model instance: {instance.invoice_number}")
                except Exception as e:
                    print(f"Failed to retrieve model: {e}")
                    # If we can't retrieve, just return the dict as is
                    return instance
        
        # Now instance should be a model instance
        print(f"Has 'has_changed' attribute: {hasattr(instance, 'has_changed')}")
        print("=" * 80)
        
        result = super().to_representation(instance)
        return result


class InvoiceCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating invoices"""
    items = InvoiceItemSerializer(many=True)
    
    class Meta:
        model = Invoice
        fields = [
            'booking', 'user', 'billing_company_name', 'billing_tax_id',
            'billing_address_line1', 'billing_address_line2',
            'billing_city', 'billing_state', 'billing_postal_code',
            'billing_country', 'notes', 'items'
        ]
    
    def create(self, validated_data):
        items_data = validated_data.pop('items')
        invoice = Invoice.objects.create(**validated_data)
        
        for item_data in items_data:
            InvoiceItem.objects.create(invoice=invoice, **item_data)
        
        # Calculate totals
        subtotal = sum(item.line_total_usd for item in invoice.items.all())
        invoice.subtotal_usd = subtotal
        invoice.tax_amount_usd = subtotal * (invoice.tax_rate / 100)
        invoice.total_usd = subtotal + invoice.tax_amount_usd - invoice.discount_amount_usd
        invoice.save()
        
        return invoice


# Optional: Add a serializer for airport lookups
class AirportSerializer(serializers.ModelSerializer):
    """Simple airport serializer for autocomplete endpoints"""
    display_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Airport
        fields = ['iata_code', 'name', 'city', 'country', 'display_name']
    
    def get_display_name(self, obj):
        return f"{obj.city} ({obj.iata_code})"