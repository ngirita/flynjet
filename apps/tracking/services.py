import requests
import json
import math
from django.utils import timezone
from django.conf import settings
from .models import FlightTrack, TrackingPosition, TrackingNotification
from apps.bookings.models import Booking
import logging

logger = logging.getLogger(__name__)

class FlightTrackingService:
    """Service for managing flight tracking data"""
    
    def __init__(self, flight_track=None):
        self.flight_track = flight_track
    
    @classmethod
    def create_track_from_booking(cls, booking):
        """Create a flight track from a booking"""
        import random
        
        # Generate flight number
        flight_number = f"FJ{booking.booking_reference[-6:]}"
        
        track, created = FlightTrack.objects.get_or_create(
            booking=booking,
            defaults={
                'flight_number': flight_number,
                'aircraft_registration': booking.aircraft.registration_number,
                'departure_time': booking.departure_datetime,
                'arrival_time': booking.arrival_datetime,
                'departure_airport': booking.departure_airport,
                'arrival_airport': booking.arrival_airport,
                'is_tracking': True,
                'data_source': 'manual'
            }
        )
        
        if created:
            logger.info(f"Created flight track for booking {booking.booking_reference}")
        
        return track
    
    def update_from_adsb(self, adsb_data):
        """Update track from ADS-B data"""
        if not self.flight_track:
            raise ValueError("No flight track provided")
        
        self.flight_track.update_position(
            latitude=adsb_data.get('lat'),
            longitude=adsb_data.get('lon'),
            altitude=adsb_data.get('alt'),
            heading=adsb_data.get('heading'),
            speed=adsb_data.get('speed')
        )
        
        # Check for notifications
        self.check_notifications(adsb_data)
        
        return self.flight_track
    
    def simulate_flight(self):
        """Simulate a flight for testing/demo"""
        if not self.flight_track:
            raise ValueError("No flight track provided")
        
        import random
        import math
        from time import sleep
        
        # Start at departure airport
        current_lat = 40.7128  # Example: JFK
        current_lon = -74.0060
        
        # End at arrival airport
        end_lat = 34.0522  # Example: LAX
        end_lon = -118.2437
        
        steps = 100
        for i in range(steps + 1):
            # Linear interpolation
            ratio = i / steps
            lat = current_lat + (end_lat - current_lat) * ratio
            lon = current_lon + (end_lon - current_lon) * ratio
            
            # Add some randomness
            lat += random.uniform(-0.1, 0.1)
            lon += random.uniform(-0.1, 0.1)
            
            # Calculate altitude (climb then cruise then descent)
            if ratio < 0.2:
                alt = 10000 + (30000 * (ratio / 0.2))
            elif ratio > 0.8:
                alt = 40000 - (30000 * ((ratio - 0.8) / 0.2))
            else:
                alt = 40000
            
            self.flight_track.update_position(
                latitude=lat,
                longitude=lon,
                altitude=alt,
                heading=math.degrees(math.atan2(end_lon - lon, end_lat - lat)),
                speed=450 + random.uniform(-20, 20)
            )
            
            # Sleep to simulate real-time (remove in production)
            sleep(0.1)
        
        return self.flight_track
    
    def check_notifications(self, data):
        """Check if any notifications should be sent"""
        if not self.flight_track:
            return
        
        # Check for significant events
        if data.get('altitude') and self.flight_track.altitude:
            alt_change = abs(data['altitude'] - self.flight_track.altitude)
            if alt_change > 1000:  # Significant altitude change
                self.create_notification(
                    'altitude',
                    f"Altitude change of {int(alt_change)} feet",
                    data
                )
        
        if data.get('speed') and self.flight_track.speed:
            speed_change = abs(data['speed'] - self.flight_track.speed)
            if speed_change > 50:  # Significant speed change
                self.create_notification(
                    'speed',
                    f"Speed change of {int(speed_change)} knots",
                    data
                )
    
    def create_notification(self, notif_type, message, data=None):
        """Create a notification"""
        if not self.flight_track:
            return
        
        notification = TrackingNotification.objects.create(
            track=self.flight_track,
            notification_type=notif_type,
            title=f"Flight {self.flight_track.flight_number} Update",
            message=message,
            data=data or {},
            send_email=True,
            send_push=True
        )
        
        # Send the notification
        notification.send()
        
        return notification
    
    def calculate_distance(self, lat1, lon1, lat2, lon2):
        """Calculate distance between two points using Haversine formula"""
        R = 3440.065  # Earth's radius in nautical miles
        
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)
        
        a = math.sin(delta_lat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        return R * c


class ExternalTrackingAPI:
    """Integration with external tracking APIs"""
    
    @classmethod
    def get_flightradar_data(cls, flight_number):
        """Get data from FlightRadar24 API"""
        # This would be implemented with actual API calls
        api_key = getattr(settings, 'FLIGHTRADAR_API_KEY', '')
        if not api_key:
            return None
        
        url = f"https://api.flightradar24.com/v1/flights/{flight_number}"
        headers = {'Authorization': f'Bearer {api_key}'}
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            logger.error(f"Error fetching FlightRadar data: {e}")
        
        return None
    
    @classmethod
    def get_adsb_exchange_data(cls, flight_number):
        """Get data from ADS-B Exchange API"""
        url = f"https://adsbexchange.com/api/v2/flights/{flight_number}"
        
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            logger.error(f"Error fetching ADS-B Exchange data: {e}")
        
        return None
    
    @classmethod
    def get_weather_data(cls, latitude, longitude):
        """Get weather data for a location"""
        api_key = getattr(settings, 'OPENWEATHER_API_KEY', '')
        if not api_key:
            return None
        
        url = f"https://api.openweathermap.org/data/2.5/weather"
        params = {
            'lat': latitude,
            'lon': longitude,
            'appid': api_key,
            'units': 'metric'
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                return {
                    'temperature': data['main']['temp'],
                    'humidity': data['main']['humidity'],
                    'wind_speed': data['wind']['speed'],
                    'wind_direction': data['wind']['deg'],
                    'conditions': data['weather'][0]['description'],
                    'icon': data['weather'][0]['icon']
                }
        except Exception as e:
            logger.error(f"Error fetching weather data: {e}")
        
        return None


class TrackingDataProcessor:
    """Process and validate tracking data"""
    
    @staticmethod
    def validate_position(latitude, longitude):
        """Validate position coordinates"""
        if latitude is None or longitude is None:
            return False
        
        if not (-90 <= latitude <= 90):
            return False
        
        if not (-180 <= longitude <= 180):
            return False
        
        return True
    
    @staticmethod
    def calculate_bearing(lat1, lon1, lat2, lon2):
        """Calculate bearing between two points"""
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lon = math.radians(lon2 - lon1)
        
        x = math.sin(delta_lon) * math.cos(lat2_rad)
        y = math.cos(lat1_rad) * math.sin(lat2_rad) - \
            math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(delta_lon)
        
        bearing = math.atan2(x, y)
        bearing = math.degrees(bearing)
        bearing = (bearing + 360) % 360
        
        return bearing
    
    @staticmethod
    def interpolate_position(pos1, pos2, fraction):
        """Interpolate between two positions"""
        lat = pos1.latitude + (pos2.latitude - pos1.latitude) * fraction
        lon = pos1.longitude + (pos2.longitude - pos1.longitude) * fraction
        
        if pos1.altitude and pos2.altitude:
            alt = pos1.altitude + (pos2.altitude - pos1.altitude) * fraction
        else:
            alt = None
        
        return {
            'latitude': lat,
            'longitude': lon,
            'altitude': alt
        }