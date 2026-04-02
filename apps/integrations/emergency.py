import requests
from django.conf import settings
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class EmergencyService:
    """Emergency procedures and alerts"""
    
    EMERGENCY_CONTACTS = {
        'global': {
            'police': '112',
            'ambulance': '112',
            'fire': '112'
        },
        'us': {
            'police': '911',
            'ambulance': '911',
            'fire': '911',
            'faa': '1-866-835-5322'
        },
        'uk': {
            'police': '999',
            'ambulance': '999',
            'fire': '999',
            'caa': '0330 022 1500'
        },
        'uae': {
            'police': '999',
            'ambulance': '998',
            'fire': '997',
            'gcaa': '971-2-4054444'
        }
    }
    
    @classmethod
    def get_emergency_contacts(cls, country_code='global'):
        """Get emergency contacts for country"""
        return cls.EMERGENCY_CONTACTS.get(country_code, cls.EMERGENCY_CONTACTS['global'])
    
    @classmethod
    def get_nearest_hospital(cls, latitude, longitude):
        """Get nearest hospital to coordinates"""
        # Would integrate with mapping API
        # Placeholder
        return {
            'name': 'General Hospital',
            'distance': '5.2 km',
            'phone': '+1234567890',
            'address': '123 Medical Blvd',
            'emergency_room': True
        }
    
    @classmethod
    def get_nearest_embassy(cls, country, latitude, longitude):
        """Get nearest embassy for country"""
        # Would need embassy database
        # Placeholder
        return {
            'country': country,
            'city': 'Washington DC',
            'address': '1600 Embassy Row',
            'phone': '+1-202-555-0123',
            'emergency_phone': '+1-202-555-0124'
        }
    
    @classmethod
    def get_weather_emergencies(cls, latitude, longitude):
        """Get weather emergencies in area"""
        emergencies = []
        
        # Check for severe weather
        weather_alerts = cls._check_weather_alerts(latitude, longitude)
        if weather_alerts:
            emergencies.extend(weather_alerts)
        
        # Check for natural disasters
        disaster_alerts = cls._check_disaster_alerts(latitude, longitude)
        if disaster_alerts:
            emergencies.extend(disaster_alerts)
        
        return emergencies
    
    @classmethod
    def _check_weather_alerts(cls, latitude, longitude):
        """Check for weather alerts"""
        # Would integrate with weather service
        # Placeholder
        return [
            {
                'type': 'severe_thunderstorm',
                'severity': 'warning',
                'message': 'Severe thunderstorm warning in effect',
                'until': datetime.now().isoformat()
            }
        ]
    
    @classmethod
    def _check_disaster_alerts(cls, latitude, longitude):
        """Check for natural disaster alerts"""
        # Would integrate with disaster monitoring services
        # Placeholder
        return []
    
    @classmethod
    def get_aircraft_emergency_procedures(cls, emergency_type):
        """Get aircraft emergency procedures"""
        procedures = {
            'engine_failure': {
                'title': 'Engine Failure',
                'steps': [
                    'Maintain aircraft control',
                    'Identify failed engine',
                    'Reduce throttle on failed engine',
                    'Feather propeller',
                    'Secure engine',
                    'Declare emergency',
                    'Land as soon as possible'
                ],
                'checklist': 'ENGINE FAILURE checklist'
            },
            'fire': {
                'title': 'Engine Fire / Fire Warning',
                'steps': [
                    'Close throttle',
                    'Fuel shutoff valve - OFF',
                    'Feather propeller',
                    'Fire extinguisher - DISCHARGE',
                    'Land immediately'
                ],
                'checklist': 'ENGINE FIRE checklist'
            },
            'emergency_descent': {
                'title': 'Emergency Descent',
                'steps': [
                    'Throttles - IDLE',
                    'Speed brakes - EXTEND',
                    'Descend to safe altitude',
                    'Level off at 10,000 feet',
                    'Assess situation'
                ],
                'checklist': 'EMERGENCY DESCENT checklist'
            },
            'loss_of_pressurization': {
                'title': 'Loss of Cabin Pressure',
                'steps': [
                    'Don oxygen mask',
                    'Establish crew communication',
                    'Begin emergency descent',
                    'Declare emergency',
                    'Land at nearest suitable airport'
                ],
                'checklist': 'CABIN ALTITUDE WARNING checklist'
            }
        }
        
        return procedures.get(emergency_type, None)
    
    @classmethod
    def get_ditching_procedures(cls):
        """Get ditching (water landing) procedures"""
        return {
            'title': 'Ditching Procedures',
            'steps': [
                'Don life vests',
                'Brief passengers',
                'Configure aircraft for ditching',
                'Establish radio communication',
                'Approach with minimum speed',
                'Land parallel to swells',
                'Evacuate immediately'
            ],
            'equipment': [
                'Life vests',
                'Life rafts',
                'Emergency locator transmitter',
                'Survival kit'
            ]
        }
    
    @classmethod
    def get_emergency_frequencies(cls):
        """Get emergency radio frequencies"""
        return {
            'international': '121.5 MHz',
            'military': '243.0 MHz',
            'guard': '121.5 MHz',
            'vfr': '122.75 MHz',
            'ifr': '128.95 MHz'
        }
    
    @classmethod
    def get_nearest_airport(cls, latitude, longitude, aircraft_range):
        """Get nearest suitable airport for emergency"""
        # Would need airport database
        # Placeholder
        return {
            'code': 'KJFK',
            'name': 'John F Kennedy International',
            'distance': '45 nm',
            'bearing': '270°',
            'runways': ['13L/31R', '13R/31L'],
            'longest_runway': '14511 ft'
        }


class EmergencyNotification:
    """Handle emergency notifications"""
    
    @classmethod
    def notify_authorities(cls, aircraft, emergency_type, location):
        """Notify relevant authorities of emergency"""
        notifications = []
        
        # Notify ATC
        notifications.append(cls._notify_atc(aircraft, emergency_type, location))
        
        # Notify company operations
        notifications.append(cls._notify_operations(aircraft, emergency_type, location))
        
        # Notify emergency contacts
        notifications.append(cls._notify_contacts(aircraft, emergency_type, location))
        
        return notifications
    
    @classmethod
    def _notify_atc(cls, aircraft, emergency_type, location):
        """Notify Air Traffic Control"""
        # Would integrate with ATC communication systems
        return {
            'recipient': 'ATC',
            'message': f"EMERGENCY: {aircraft.registration} - {emergency_type} at {location}",
            'sent': True,
            'timestamp': datetime.now().isoformat()
        }
    
    @classmethod
    def _notify_operations(cls, aircraft, emergency_type, location):
        """Notify company operations center"""
        # Would send email/SMS to operations
        return {
            'recipient': 'Operations Center',
            'message': f"EMERGENCY: {aircraft.registration} - {emergency_type} at {location}",
            'sent': True,
            'timestamp': datetime.now().isoformat()
        }
    
    @classmethod
    def _notify_contacts(cls, aircraft, emergency_type, location):
        """Notify emergency contacts"""
        # Would notify designated emergency contacts
        return {
            'recipient': 'Emergency Contacts',
            'message': f"EMERGENCY: {aircraft.registration} - {emergency_type} at {location}",
            'sent': True,
            'timestamp': datetime.now().isoformat()
        }