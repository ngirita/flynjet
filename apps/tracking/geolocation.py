import math  
import requests
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class GeolocationService:
    """Geolocation and mapping services"""
    
    @classmethod
    def geocode_airport(cls, airport_code):
        """Get coordinates for airport code"""
        # In production, use a proper airport database or API
        airport_coords = {
            'JFK': {'lat': 40.6413, 'lng': -73.7781, 'name': 'John F Kennedy International'},
            'LAX': {'lat': 33.9416, 'lng': -118.4085, 'name': 'Los Angeles International'},
            'LHR': {'lat': 51.4700, 'lng': -0.4543, 'name': 'London Heathrow'},
            'CDG': {'lat': 49.0097, 'lng': 2.5479, 'name': 'Paris Charles de Gaulle'},
            'DXB': {'lat': 25.2532, 'lng': 55.3657, 'name': 'Dubai International'},
            'HKG': {'lat': 22.3080, 'lng': 113.9185, 'name': 'Hong Kong International'},
        }
        
        return airport_coords.get(airport_code.upper())
    
    @classmethod
    def reverse_geocode(cls, lat, lng):
        """Get location name from coordinates"""
        if not settings.GOOGLE_MAPS_API_KEY:
            return None
        
        url = "https://maps.googleapis.com/maps/api/geocode/json"
        params = {
            'latlng': f"{lat},{lng}",
            'key': settings.GOOGLE_MAPS_API_KEY
        }
        
        try:
            response = requests.get(url, params=params, timeout=5)
            data = response.json()
            
            if data['status'] == 'OK' and data['results']:
                return data['results'][0]['formatted_address']
        except Exception as e:
            logger.error(f"Reverse geocoding error: {e}")
        
        return None
    
    @classmethod
    def get_timezone(cls, lat, lng):
        """Get timezone for coordinates"""
        if not settings.GOOGLE_MAPS_API_KEY:
            return 'UTC'
        
        url = "https://maps.googleapis.com/maps/api/timezone/json"
        params = {
            'location': f"{lat},{lng}",
            'timestamp': 0,
            'key': settings.GOOGLE_MAPS_API_KEY
        }
        
        try:
            response = requests.get(url, params=params, timeout=5)
            data = response.json()
            
            if data['status'] == 'OK':
                return data['timeZoneId']
        except Exception as e:
            logger.error(f"Timezone API error: {e}")
        
        return 'UTC'
    
    @classmethod
    def calculate_great_circle(cls, lat1, lng1, lat2, lng2):
        """Calculate great circle route between two points"""
        import math
        
        lat1_rad = math.radians(lat1)
        lng1_rad = math.radians(lng1)
        lat2_rad = math.radians(lat2)
        lng2_rad = math.radians(lng2)
        
        # Calculate waypoints (simplified - 10 points)
        waypoints = []
        steps = 10
        
        for i in range(steps + 1):
            f = i / steps
            # Spherical interpolation
            A = math.sin((1 - f) * math.pi/2)
            B = math.sin(f * math.pi/2)
            
            x = A * math.cos(lat1_rad) * math.cos(lng1_rad) + B * math.cos(lat2_rad) * math.cos(lng2_rad)
            y = A * math.cos(lat1_rad) * math.sin(lng1_rad) + B * math.cos(lat2_rad) * math.sin(lng2_rad)
            z = A * math.sin(lat1_rad) + B * math.sin(lat2_rad)
            
            lat = math.atan2(z, math.sqrt(x**2 + y**2))
            lng = math.atan2(y, x)
            
            waypoints.append({
                'lat': math.degrees(lat),
                'lng': math.degrees(lng)
            })
        
        return waypoints
    
    @classmethod
    def get_elevation(cls, lat, lng):
        """Get elevation for coordinates"""
        url = "https://api.open-elevation.com/api/v1/lookup"
        params = {'locations': f"{lat},{lng}"}
        
        try:
            response = requests.get(url, params=params, timeout=5)
            data = response.json()
            
            if data.get('results'):
                return data['results'][0]['elevation']
        except Exception as e:
            logger.error(f"Elevation API error: {e}")
        
        return 0
    
    @classmethod
    def get_map_tile_url(cls, lat, lng, zoom=10):
        """Get map tile URL for coordinates"""
        # Using OpenStreetMap tiles
        return f"https://tile.openstreetmap.org/{zoom}/{int(lat)}/{int(lng)}.png"
    
    @classmethod
    def calculate_bounding_box(cls, lat, lng, radius_km):
        """Calculate bounding box around point"""
        # Approximate conversion: 1 degree latitude = 111 km
        lat_delta = radius_km / 111
        lng_delta = radius_km / (111 * math.cos(math.radians(lat)))
        
        return {
            'min_lat': lat - lat_delta,
            'max_lat': lat + lat_delta,
            'min_lng': lng - lng_delta,
            'max_lng': lng + lng_delta
        }