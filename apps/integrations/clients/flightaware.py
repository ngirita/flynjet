import requests
from django.conf import settings
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class FlightAwareClient:
    """Client for FlightAware AeroAPI"""
    
    BASE_URL = "https://aeroapi.flightaware.com/aeroapi"
    
    def __init__(self):
        self.api_key = settings.FLIGHTAWARE_API_KEY
        self.session = requests.Session()
        self.session.headers.update({
            'x-apikey': self.api_key,
            'Accept': 'application/json'
        })
    
    def get_flight(self, ident):
        """Get flight information by ID or registration"""
        if not self.api_key:
            logger.error("FlightAware API key not configured")
            return None
        
        try:
            response = self.session.get(
                f"{self.BASE_URL}/flights/{ident}",
                timeout=10
            )
            response.raise_for_status()
            
            data = response.json()
            
            return {
                'flight_id': data.get('flight_id'),
                'ident': data.get('ident'),
                'aircraft_type': data.get('aircraft_type'),
                'origin': data.get('origin', {}).get('code'),
                'destination': data.get('destination', {}).get('code'),
                'departure_time': data.get('scheduled_out'),
                'arrival_time': data.get('scheduled_in'),
                'status': data.get('status'),
                'gate_origin': data.get('gate_origin'),
                'gate_destination': data.get('gate_destination'),
                'airline': data.get('airline')
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"FlightAware API error: {e}")
            return None
    
    def get_flight_track(self, flight_id):
        """Get flight track positions"""
        if not self.api_key:
            return None
        
        try:
            response = self.session.get(
                f"{self.BASE_URL}/flights/{flight_id}/track",
                timeout=10
            )
            response.raise_for_status()
            
            data = response.json()
            
            positions = []
            for position in data.get('positions', []):
                positions.append({
                    'timestamp': position.get('timestamp'),
                    'latitude': position.get('lat'),
                    'longitude': position.get('lon'),
                    'altitude': position.get('alt'),
                    'ground_speed': position.get('gs'),
                    'heading': position.get('heading')
                })
            
            return {
                'flight_id': flight_id,
                'positions': positions
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"FlightAware track error: {e}")
            return None
    
    def get_flights_by_aircraft(self, registration, days=7):
        """Get flights by aircraft registration"""
        if not self.api_key:
            return None
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        params = {
            'start': start_date.isoformat(),
            'end': end_date.isoformat(),
            'max_pages': 1
        }
        
        try:
            response = self.session.get(
                f"{self.BASE_URL}/aircraft/{registration}/flights",
                params=params,
                timeout=10
            )
            response.raise_for_status()
            
            data = response.json()
            
            flights = []
            for flight in data.get('flights', []):
                flights.append({
                    'flight_id': flight.get('flight_id'),
                    'ident': flight.get('ident'),
                    'origin': flight.get('origin', {}).get('code'),
                    'destination': flight.get('destination', {}).get('code'),
                    'departure_time': flight.get('scheduled_out'),
                    'arrival_time': flight.get('scheduled_in'),
                    'status': flight.get('status')
                })
            
            return flights
            
        except requests.exceptions.RequestException as e:
            logger.error(f"FlightAware aircraft flights error: {e}")
            return None
    
    def get_airport_departures(self, airport_code, howMany=15):
        """Get departures from airport"""
        if not self.api_key:
            return None
        
        params = {
            'howMany': howMany
        }
        
        try:
            response = self.session.get(
                f"{self.BASE_URL}/airports/{airport_code}/flights/scheduled_departures",
                params=params,
                timeout=10
            )
            response.raise_for_status()
            
            data = response.json()
            
            flights = []
            for flight in data.get('scheduled_departures', []):
                flights.append({
                    'ident': flight.get('ident'),
                    'destination': flight.get('destination', {}).get('code'),
                    'departure_time': flight.get('scheduled_out'),
                    'airline': flight.get('airline'),
                    'gate': flight.get('gate_origin'),
                    'status': flight.get('status')
                })
            
            return flights
            
        except requests.exceptions.RequestException as e:
            logger.error(f"FlightAware departures error: {e}")
            return None
    
    def get_airport_arrivals(self, airport_code, howMany=15):
        """Get arrivals to airport"""
        if not self.api_key:
            return None
        
        params = {
            'howMany': howMany
        }
        
        try:
            response = self.session.get(
                f"{self.BASE_URL}/airports/{airport_code}/flights/scheduled_arrivals",
                params=params,
                timeout=10
            )
            response.raise_for_status()
            
            data = response.json()
            
            flights = []
            for flight in data.get('scheduled_arrivals', []):
                flights.append({
                    'ident': flight.get('ident'),
                    'origin': flight.get('origin', {}).get('code'),
                    'arrival_time': flight.get('scheduled_in'),
                    'airline': flight.get('airline'),
                    'gate': flight.get('gate_destination'),
                    'status': flight.get('status')
                })
            
            return flights
            
        except requests.exceptions.RequestException as e:
            logger.error(f"FlightAware arrivals error: {e}")
            return None
    
    def get_weather(self, airport_code):
        """Get weather at airport"""
        if not self.api_key:
            return None
        
        try:
            response = self.session.get(
                f"{self.BASE_URL}/airports/{airport_code}/weather",
                timeout=10
            )
            response.raise_for_status()
            
            data = response.json()
            
            return {
                'temp': data.get('temp'),
                'dewpoint': data.get('dewpoint'),
                'wind_speed': data.get('wind_speed'),
                'wind_direction': data.get('wind_direction'),
                'visibility': data.get('visibility'),
                'conditions': data.get('conditions'),
                'metar': data.get('metar')
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"FlightAware weather error: {e}")
            return None
    
    def get_notams(self, airport_code):
        """Get NOTAMs for airport"""
        if not self.api_key:
            return None
        
        try:
            response = self.session.get(
                f"{self.BASE_URL}/airports/{airport_code}/notams",
                timeout=10
            )
            response.raise_for_status()
            
            data = response.json()
            
            notams = []
            for notam in data.get('notams', []):
                notams.append({
                    'id': notam.get('notam_id'),
                    'type': notam.get('type'),
                    'message': notam.get('message'),
                    'start_time': notam.get('start_time'),
                    'end_time': notam.get('end_time')
                })
            
            return notams
            
        except requests.exceptions.RequestException as e:
            logger.error(f"FlightAware NOTAM error: {e}")
            return None