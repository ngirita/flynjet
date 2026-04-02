import math
import json
from django.utils import timezone
from datetime import datetime

def calculate_distance(lat1, lon1, lat2, lon2):
    """Calculate distance between two points using Haversine formula"""
    R = 3440.065  # Earth's radius in nautical miles
    
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    
    a = math.sin(delta_lat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    
    return R * c

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

def calculate_eta(distance, speed):
    """Calculate estimated time of arrival"""
    if speed <= 0:
        return None
    hours = distance / speed
    return timezone.now() + timezone.timedelta(hours=hours)

def format_speed(speed_knots):
    """Format speed with units"""
    if speed_knots is None:
        return "N/A"
    return f"{speed_knots:.0f} kts"

def format_altitude(altitude_feet):
    """Format altitude with units"""
    if altitude_feet is None:
        return "N/A"
    if altitude_feet > 30000:
        return f"{altitude_feet/1000:.0f}K ft"
    return f"{altitude_feet:.0f} ft"

def format_heading(heading_degrees):
    """Format heading as direction"""
    if heading_degrees is None:
        return "N/A"
    
    directions = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE',
                  'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW']
    idx = round(heading_degrees / 22.5) % 16
    return f"{heading_degrees:.0f}° {directions[idx]}"

def generate_flight_number(booking):
    """Generate flight number from booking"""
    return f"FJ{booking.booking_reference[-6:]}"

def validate_coordinates(lat, lon):
    """Validate coordinates"""
    if lat is None or lon is None:
        return False
    if not (-90 <= lat <= 90):
        return False
    if not (-180 <= lon <= 180):
        return False
    return True

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

def create_tracking_summary(track):
    """Create tracking summary for display"""
    return {
        'flight_number': track.flight_number,
        'aircraft': track.aircraft_registration,
        'from': track.departure_airport,
        'to': track.arrival_airport,
        'progress': track.progress_percentage,
        'position': {
            'lat': track.latitude,
            'lng': track.longitude,
            'alt': format_altitude(track.altitude),
            'speed': format_speed(track.speed),
            'heading': format_heading(track.heading)
        },
        'times': {
            'departure': track.departure_time.isoformat() if track.departure_time else None,
            'estimated': track.estimated_arrival.isoformat() if track.estimated_arrival else None,
            'last_update': track.last_update.isoformat() if track.last_update else None
        }
    }

def parse_adsb_data(data):
    """Parse ADS-B data"""
    try:
        return {
            'lat': data.get('lat'),
            'lon': data.get('lon'),
            'alt': data.get('altitude'),
            'speed': data.get('speed'),
            'heading': data.get('track'),
            'vert_rate': data.get('vert_rate'),
            'squawk': data.get('squawk'),
            'callsign': data.get('flight'),
            'timestamp': datetime.fromtimestamp(data.get('timestamp', 0))
        }
    except:
        return None

def generate_tracking_token():
    """Generate unique tracking token"""
    import uuid
    return uuid.uuid4()

def get_flight_phase(altitude, speed, ground):
    """Determine flight phase based on parameters"""
    if altitude is None or speed is None:
        return 'unknown'
    
    if altitude < 1000:
        if speed < 50:
            return 'taxi'
        elif speed < 150:
            return 'takeoff'
        else:
            return 'landing'
    elif altitude < 10000:
        return 'climb' if speed < 250 else 'approach'
    elif altitude > 25000:
        return 'cruise'
    else:
        return 'enroute'