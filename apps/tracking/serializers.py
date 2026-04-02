from rest_framework import serializers
from .models import FlightTrack, TrackingShare, FlightAlert, TrackingPosition

class TrackingPositionSerializer(serializers.ModelSerializer):
    class Meta:
        model = TrackingPosition
        fields = ['latitude', 'longitude', 'altitude', 'heading', 'speed', 'timestamp']


class FlightTrackSerializer(serializers.ModelSerializer):
    booking_reference = serializers.CharField(source='booking.booking_reference', read_only=True)
    
    class Meta:
        model = FlightTrack
        fields = [
            'id', 'flight_number', 'booking_reference', 'aircraft_registration',
            'latitude', 'longitude', 'altitude', 'heading', 'speed',
            'progress_percentage', 'departure_airport', 'arrival_airport',
            'departure_time', 'arrival_time', 'estimated_arrival',
            'last_update', 'is_tracking'
        ]


class FlightTrackDetailSerializer(serializers.ModelSerializer):
    positions = TrackingPositionSerializer(source='position_history', many=True, read_only=True)
    
    class Meta:
        model = FlightTrack
        fields = '__all__'


class TrackingShareSerializer(serializers.ModelSerializer):
    share_url = serializers.SerializerMethodField()
    
    class Meta:
        model = TrackingShare
        fields = ['id', 'token', 'share_url', 'expires_at', 'views', 'created_at']
        read_only_fields = ['token', 'views', 'created_at']
    
    def get_share_url(self, obj):
        return f"/tracking/share/{obj.token}/"


class FlightAlertSerializer(serializers.ModelSerializer):
    class Meta:
        model = FlightAlert
        fields = '__all__'
        read_only_fields = ['user', 'last_triggered', 'trigger_count']