import requests
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class OpenWeatherClient:
    """Client for OpenWeatherMap API"""
    
    BASE_URL = "https://api.openweathermap.org/data/2.5"
    
    def __init__(self):
        self.api_key = settings.OPENWEATHER_API_KEY
        self.session = requests.Session()
        self.session.headers.update({
            'Accept': 'application/json'
        })
    
    def get_weather(self, location):
        """Get current weather for location"""
        if not self.api_key:
            logger.error("OpenWeather API key not configured")
            return None
        
        try:
            # Check if location is coordinates or city name
            if ',' in location and all(part.replace('.', '').replace('-', '').isdigit() for part in location.split(',')):
                # Coordinates format: lat,lon
                lat, lon = location.split(',')
                params = {
                    'lat': lat.strip(),
                    'lon': lon.strip(),
                    'appid': self.api_key,
                    'units': 'metric'
                }
                url = f"{self.BASE_URL}/weather"
            else:
                # City name
                params = {
                    'q': location,
                    'appid': self.api_key,
                    'units': 'metric'
                }
                url = f"{self.BASE_URL}/weather"
            
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            # Add lat/lon if not provided
            if 'coord' in data:
                data['lat'] = data['coord']['lat']
                data['lon'] = data['coord']['lon']
            
            return data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching weather for {location}: {e}")
            return None
    
    def get_forecast(self, location, days=5):
        """Get weather forecast"""
        if not self.api_key:
            logger.error("OpenWeather API key not configured")
            return None
        
        try:
            # Get coordinates first
            weather = self.get_weather(location)
            if not weather or 'lat' not in weather:
                return None
            
            params = {
                'lat': weather['lat'],
                'lon': weather['lon'],
                'appid': self.api_key,
                'units': 'metric',
                'cnt': days * 8  # 8 forecasts per day
            }
            
            response = self.session.get(f"{self.BASE_URL}/forecast", params=params, timeout=10)
            response.raise_for_status()
            
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching forecast for {location}: {e}")
            return None