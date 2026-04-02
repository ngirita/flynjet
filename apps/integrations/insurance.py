import requests
from django.conf import settings
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class InsuranceService:
    """Aviation insurance verification and claims"""
    
    INSURANCE_PROVIDERS = {
        'global_aerospace': {
            'api_url': settings.GLOBAL_AEROSPACE_API_URL,
            'api_key': settings.GLOBAL_AEROSPACE_API_KEY,
            'enabled': bool(settings.GLOBAL_AEROSPACE_API_KEY)
        },
        'aig_aviation': {
            'api_url': settings.AIG_AVIATION_API_URL,
            'api_key': settings.AIG_AVIATION_API_KEY,
            'enabled': bool(settings.AIG_AVIATION_API_KEY)
        }
    }
    
    @classmethod
    def verify_insurance(cls, aircraft_registration):
        """Verify insurance coverage for aircraft"""
        # Check local database first
        from apps.fleet.models import Aircraft
        try:
            aircraft = Aircraft.objects.get(registration_number=aircraft_registration)
            if aircraft.insurance_policy_number and aircraft.insurance_expiry:
                if aircraft.insurance_expiry > datetime.now().date():
                    return {
                        'verified': True,
                        'policy_number': aircraft.insurance_policy_number,
                        'expiry': aircraft.insurance_expiry,
                        'source': 'database'
                    }
        except Aircraft.DoesNotExist:
            pass
        
        # Check with insurance providers
        for provider_name, provider in cls.INSURANCE_PROVIDERS.items():
            if provider['enabled']:
                result = cls._check_with_provider(provider_name, aircraft_registration)
                if result:
                    return result
        
        return {'verified': False, 'message': 'Insurance not found'}
    
    @classmethod
    def _check_with_provider(cls, provider, aircraft_registration):
        """Check insurance with specific provider"""
        if provider == 'global_aerospace':
            return cls._check_global_aerospace(aircraft_registration)
        elif provider == 'aig_aviation':
            return cls._check_aig(aircraft_registration)
        
        return None
    
    @classmethod
    def _check_global_aerospace(cls, aircraft_registration):
        """Check with Global Aerospace"""
        try:
            params = {
                'registration': aircraft_registration,
                'api_key': cls.INSURANCE_PROVIDERS['global_aerospace']['api_key']
            }
            
            response = requests.get(
                f"{cls.INSURANCE_PROVIDERS['global_aerospace']['api_url']}/verify",
                params=params,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'verified': data.get('active', False),
                    'policy_number': data.get('policy_number'),
                    'expiry': datetime.strptime(data.get('expiry'), '%Y-%m-%d').date(),
                    'provider': 'Global Aerospace',
                    'source': 'api'
                }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Global Aerospace API error: {e}")
        
        return None
    
    @classmethod
    def _check_aig(cls, aircraft_registration):
        """Check with AIG Aviation"""
        try:
            headers = {
                'Authorization': f"Bearer {cls.INSURANCE_PROVIDERS['aig_aviation']['api_key']}"
            }
            
            response = requests.get(
                f"{cls.INSURANCE_PROVIDERS['aig_aviation']['api_url']}/aircraft/{aircraft_registration}",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'verified': data.get('in_force', False),
                    'policy_number': data.get('policy_id'),
                    'expiry': datetime.strptime(data.get('expiration_date'), '%Y-%m-%d').date(),
                    'provider': 'AIG Aviation',
                    'source': 'api'
                }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"AIG Aviation API error: {e}")
        
        return None
    
    @classmethod
    def get_coverage_details(cls, policy_number):
        """Get detailed coverage information"""
        # Would fetch from provider
        # Placeholder
        return {
            'policy_number': policy_number,
            'coverage_types': [
                'Hull - Physical Damage',
                'Liability - Bodily Injury',
                'Liability - Property Damage',
                'Passenger Liability',
                'Medical Payments'
            ],
            'limits': {
                'hull': '$25,000,000',
                'liability': '$100,000,000',
                'passenger': '$50,000,000'
            },
            'deductibles': {
                'in_motion': '$50,000',
                'not_in_motion': '$25,000'
            }
        }
    
    @classmethod
    def file_claim(cls, claim_data):
        """File an insurance claim"""
        claim_number = cls._generate_claim_number()
        
        # Store in database
        from .models import InsuranceClaim
        claim = InsuranceClaim.objects.create(
            claim_number=claim_number,
            policy_number=claim_data.get('policy_number'),
            incident_date=claim_data.get('incident_date'),
            description=claim_data.get('description'),
            estimated_amount=claim_data.get('estimated_amount'),
            status='pending'
        )
        
        # Notify insurance provider
        cls._notify_provider(claim)
        
        return {
            'claim_number': claim_number,
            'status': 'filed',
            'estimated_processing_days': 5
        }
    
    @classmethod
    def _generate_claim_number(cls):
        """Generate unique claim number"""
        import random
        import string
        timestamp = datetime.now().strftime('%Y%m')
        random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        return f"CLM{timestamp}{random_str}"
    
    @classmethod
    def _notify_provider(cls, claim):
        """Notify insurance provider of claim"""
        # Would send to provider API
        logger.info(f"Claim {claim.claim_number} filed")
        return True
    
    @classmethod
    def get_claim_status(cls, claim_number):
        """Get status of insurance claim"""
        from .models import InsuranceClaim
        try:
            claim = InsuranceClaim.objects.get(claim_number=claim_number)
            return {
                'claim_number': claim.claim_number,
                'status': claim.status,
                'filed_date': claim.created_at,
                'last_updated': claim.updated_at,
                'estimated_amount': claim.estimated_amount,
                'approved_amount': claim.approved_amount
            }
        except InsuranceClaim.DoesNotExist:
            return {'error': 'Claim not found'}