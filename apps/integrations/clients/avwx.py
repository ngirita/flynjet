import requests
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class AviationStackClient:
    """Client for AviationStack API (flight data)"""
    
    BASE_URL = "http://api.aviationstack.com/v1"
    
    def __init__(self):
        self.api_key = settings.AVIATIONSTACK_API_KEY
        self.session = requests.Session()
    
    def get_flights(self, flight_number=None, dep_iata=None, arr_iata=None):
        """Get flight information"""
        if not self.api_key:
            logger.error("AviationStack API key not configured")
            return None
        
        params = {
            'access_key': self.api_key,
            'limit': 100
        }
        
        if flight_number:
            params['flight_number'] = flight_number
        if dep_iata:
            params['dep_iata'] = dep_iata
        if arr_iata:
            params['arr_iata'] = arr_iata
        
        try:
            response = self.session.get(f"{self.BASE_URL}/flights", params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get('error'):
                logger.error(f"AviationStack API error: {data['error']}")
                return None
            
            return data.get('data', [])
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching flights: {e}")
            return None
    
    def get_airlines(self):
        """Get airlines data"""
        if not self.api_key:
            return None
        
        params = {
            'access_key': self.api_key
        }
        
        try:
            response = self.session.get(f"{self.BASE_URL}/airlines", params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            return data.get('data', [])
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching airlines: {e}")
            return None
    
    def get_airports(self, iata_code=None):
        """Get airports data"""
        if not self.api_key:
            return None
        
        params = {
            'access_key': self.api_key
        }
        
        if iata_code:
            params['iata_code'] = iata_code
        
        try:
            response = self.session.get(f"{self.BASE_URL}/airports", params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            return data.get('data', [])
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching airports: {e}")
            return None


class FlightAwareClient:
    """Client for FlightAware API (flight tracking)"""
    
    BASE_URL = "https://aeroapi.flightaware.com/aeroapi"
    
    def __init__(self):
        self.api_key = settings.FLIGHTAWARE_API_KEY
        self.session = requests.Session()
        self.session.headers.update({
            'x-apikey': self.api_key
        })
    
    def get_flight(self, ident):
        """Get flight information by ID or registration"""
        if not self.api_key:
            logger.error("FlightAware API key not configured")
            return None
        
        try:
            response = self.session.get(f"{self.BASE_URL}/flights/{ident}", timeout=10)
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching flight {ident}: {e}")
            return None
    
    def get_flights_by_aircraft(self, registration, days=7):
        """Get flights by aircraft registration"""
        if not self.api_key:
            return None
        
        params = {
            'max_pages': 1
        }
        
        try:
            response = self.session.get(
                f"{self.BASE_URL}/aircraft/{registration}/flights",
                params=params,
                timeout=10
            )
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching flights for {registration}: {e}")
            return None
    
    def get_flight_track(self, flight_id):
        """Get flight track positions"""
        if not self.api_key:
            return None
        
        try:
            response = self.session.get(f"{self.BASE_URL}/flights/{flight_id}/track", timeout=10)
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching track for {flight_id}: {e}")
            return None