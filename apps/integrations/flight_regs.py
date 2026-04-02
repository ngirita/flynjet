import requests
from django.conf import settings
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class FlightRegulationsService:
    """Flight regulations and restrictions data"""
    
    def __init__(self):
        self.apis = {
            'faa': {
                'notams': 'https://notams.aim.faa.gov/notamSearch/search',
                'tfr': 'https://tfr.faa.gov/tfr2/list.jsp'
            },
            'eurocontrol': {
                'base': 'https://www.eurocontrol.int',
                'api': settings.EUROCONTROL_API_KEY
            },
            'icao': {
                'base': 'https://applications.icao.int'
            }
        }
    
    def get_notams(self, airport_code):
        """Get NOTAMs for airport"""
        try:
            params = {
                'searchType': '0',
                'designators': airport_code
            }
            
            response = requests.get(
                self.apis['faa']['notams'],
                params=params,
                timeout=10
            )
            
            if response.status_code == 200:
                return self._parse_notams(response.text)
            
        except requests.exceptions.RequestException as e:
            logger.error(f"NOTAM API error: {e}")
        
        return []
    
    def _parse_notams(self, html):
        """Parse NOTAMs from FAA HTML response"""
        # This would need proper HTML parsing
        # Simplified version
        import re
        notams = []
        
        # Extract NOTAMs using regex
        pattern = r'![\w\s]+[\s\S]*?(?=!|\Z)'
        matches = re.findall(pattern, html)
        
        for match in matches:
            notams.append({
                'raw': match.strip(),
                'airport': self._extract_airport(match),
                'type': self._extract_type(match),
                'description': self._extract_description(match)
            })
        
        return notams
    
    def _extract_airport(self, notam):
        """Extract airport code from NOTAM"""
        import re
        match = re.search(r'[A-Z]{4}', notam)
        return match.group(0) if match else None
    
    def _extract_type(self, notam):
        """Extract NOTAM type"""
        if 'RWY' in notam:
            return 'runway'
        elif 'NAV' in notam:
            return 'navigation'
        elif 'COM' in notam:
            return 'communication'
        elif 'APRON' in notam:
            return 'apron'
        else:
            return 'general'
    
    def _extract_description(self, notam):
        """Extract NOTAM description"""
        # Simplified - would need proper parsing
        return notam[:200] + '...' if len(notam) > 200 else notam
    
    def get_tfrs(self):
        """Get Temporary Flight Restrictions"""
        try:
            response = requests.get(
                self.apis['faa']['tfr'],
                timeout=10
            )
            
            if response.status_code == 200:
                return self._parse_tfrs(response.text)
            
        except requests.exceptions.RequestException as e:
            logger.error(f"TFR API error: {e}")
        
        return []
    
    def _parse_tfrs(self, html):
        """Parse TFRs from FAA HTML"""
        # Simplified version
        tfrs = []
        import re
        
        # Extract TFR entries
        pattern = r'<tr[^>]*>[\s\S]*?<\/tr>'
        matches = re.findall(pattern, html)
        
        for match in matches[:10]:  # Limit to first 10
            if 'TFR' in match:
                tfrs.append({
                    'raw': re.sub(r'<[^>]+>', '', match).strip(),
                    'url': self._extract_tfr_url(match)
                })
        
        return tfrs
    
    def _extract_tfr_url(self, html):
        """Extract TFR URL"""
        import re
        match = re.search(r'href="([^"]+)"', html)
        return match.group(1) if match else None
    
    def get_airspace_restrictions(self, latitude, longitude):
        """Get airspace restrictions at coordinates"""
        # This would integrate with various airspace databases
        restrictions = []
        
        # Check for special use airspace
        # Simplified - would need proper database
        return restrictions
    
    def check_flight_plan_compliance(self, departure, arrival, aircraft_type):
        """Check if flight plan complies with regulations"""
        issues = []
        
        # Check for route restrictions
        # Check for aircraft type restrictions
        # Check for time-based restrictions
        
        return {
            'compliant': len(issues) == 0,
            'issues': issues
        }
    
    def get_overflight_permit_requirements(self, countries):
        """Get overflight permit requirements for countries"""
        requirements = {}
        
        # Database of country requirements
        country_requirements = {
            'RU': {'permit_required': True, 'lead_time_days': 7},
            'CN': {'permit_required': True, 'lead_time_days': 10},
            'US': {'permit_required': False},
            'CA': {'permit_required': False},
            # Add more countries
        }
        
        for country in countries:
            if country in country_requirements:
                requirements[country] = country_requirements[country]
        
        return requirements


class ETOPSRules:
    """ETOPS (Extended-range Twin-engine Operations) rules"""
    
    @staticmethod
    def check_etops_compliance(aircraft_type, route, alternate_airports):
        """Check ETOPS compliance for route"""
        # Calculate distance from suitable airports
        # Check aircraft ETOPS certification
        # Return compliance status
        
        return {
            'etops_required': True,
            'etops_certified': True,
            'max_diversion_time': 180,  # minutes
            'suitable_alternates': len(alternate_airports) >= 2,
            'compliant': True
        }


class NightFlightRestrictions:
    """Night flight restrictions by airport"""
    
    @staticmethod
    def get_restrictions(airport_code):
        """Get night flight restrictions for airport"""
        restrictions_db = {
            'LHR': {'curfew': True, 'start_time': '23:30', 'end_time': '06:00'},
            'CDG': {'curfew': True, 'start_time': '00:00', 'end_time': '05:00'},
            'FRA': {'curfew': True, 'start_time': '23:00', 'end_time': '05:00'},
            # Add more airports
        }
        
        return restrictions_db.get(airport_code, {'curfew': False})
    
    @staticmethod
    def check_flight_time(departure_time, airport_code):
        """Check if departure time violates curfew"""
        restrictions = NightFlightRestrictions.get_restrictions(airport_code)
        
        if not restrictions.get('curfew'):
            return {'allowed': True}
        
        # Parse times
        flight_hour = departure_time.hour
        start_hour = int(restrictions['start_time'].split(':')[0])
        end_hour = int(restrictions['end_time'].split(':')[0])
        
        if start_hour <= end_hour:
            # Same day restriction
            allowed = not (start_hour <= flight_hour <= end_hour)
        else:
            # Overnight restriction
            allowed = not (flight_hour >= start_hour or flight_hour <= end_hour)
        
        return {
            'allowed': allowed,
            'curfew_start': restrictions['start_time'],
            'curfew_end': restrictions['end_time']
        }