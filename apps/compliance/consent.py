from django.utils import timezone
from .models import ConsentRecord
import logging

logger = logging.getLogger(__name__)

class ConsentManager:
    """Manage user consent for data processing"""
    
    CONSENT_TYPES = {
        'terms': {
            'name': 'Terms of Service',
            'version': '2.1',
            'required': True,
            'description': 'Accept our terms of service'
        },
        'privacy': {
            'name': 'Privacy Policy',
            'version': '3.0',
            'required': True,
            'description': 'Accept our privacy policy'
        },
        'marketing': {
            'name': 'Marketing Communications',
            'version': '1.5',
            'required': False,
            'description': 'Receive marketing emails and offers'
        },
        'cookies': {
            'name': 'Cookie Consent',
            'version': '2.0',
            'required': False,
            'description': 'Allow non-essential cookies'
        },
        'data_processing': {
            'name': 'Data Processing',
            'version': '1.2',
            'required': True,
            'description': 'Allow processing of personal data'
        },
        'third_party': {
            'name': 'Third Party Sharing',
            'version': '1.0',
            'required': False,
            'description': 'Allow sharing data with partners'
        }
    }
    
    @classmethod
    def get_consent_status(cls, user):
        """Get consent status for all types"""
        status = {}
        
        for consent_type, config in cls.CONSENT_TYPES.items():
            latest = ConsentRecord.objects.filter(
                user=user,
                consent_type=consent_type
            ).order_by('-created_at').first()
            
            status[consent_type] = {
                'granted': latest.granted if latest else False,
                'version': latest.version if latest else config['version'],
                'date': latest.created_at if latest else None,
                'required': config['required'],
                'name': config['name'],
                'description': config['description'],
                'needs_update': cls.needs_update(user, consent_type)
            }
        
        return status
    
    @classmethod
    def needs_update(cls, user, consent_type):
        """Check if consent needs to be updated"""
        latest = ConsentRecord.objects.filter(
            user=user,
            consent_type=consent_type
        ).order_by('-created_at').first()
        
        if not latest:
            return True
        
        current_version = cls.CONSENT_TYPES[consent_type]['version']
        return latest.version != current_version
    
    @classmethod
    def record_consent(cls, user, consent_type, granted, ip_address=None, user_agent=None):
        """Record user consent"""
        config = cls.CONSENT_TYPES.get(consent_type)
        if not config:
            raise ValueError(f"Invalid consent type: {consent_type}")
        
        consent = ConsentRecord.objects.create(
            user=user,
            consent_type=consent_type,
            version=config['version'],
            granted=granted,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        logger.info(f"Consent recorded for {user.email}: {consent_type}={granted}")
        return consent
    
    @classmethod
    def withdraw_consent(cls, user, consent_type, ip_address=None):
        """Withdraw previously given consent"""
        latest = ConsentRecord.objects.filter(
            user=user,
            consent_type=consent_type,
            granted=True
        ).order_by('-created_at').first()
        
        if latest:
            latest.withdraw(ip_address)
            logger.info(f"Consent withdrawn for {user.email}: {consent_type}")
            return True
        
        return False
    
    @classmethod
    def check_consent(cls, user, consent_type):
        """Check if user has given consent"""
        latest = ConsentRecord.objects.filter(
            user=user,
            consent_type=consent_type
        ).order_by('-created_at').first()
        
        return latest.granted if latest else False
    
    @classmethod
    def get_required_consents(cls):
        """Get list of required consents"""
        return [
            ct for ct, config in cls.CONSENT_TYPES.items()
            if config['required']
        ]
    
    @classmethod
    def check_all_required(cls, user):
        """Check if user has given all required consents"""
        for consent_type in cls.get_required_consents():
            if not cls.check_consent(user, consent_type):
                return False
        return True
    
    @classmethod
    def get_consent_history(cls, user, consent_type=None):
        """Get consent history for user"""
        queryset = ConsentRecord.objects.filter(user=user)
        
        if consent_type:
            queryset = queryset.filter(consent_type=consent_type)
        
        return queryset.order_by('-created_at')


class CookieConsent:
    """Manage cookie consent"""
    
    COOKIE_CATEGORIES = {
        'essential': {
            'name': 'Essential Cookies',
            'description': 'Required for basic site functionality',
            'always_on': True
        },
        'functional': {
            'name': 'Functional Cookies',
            'description': 'Remember your preferences',
            'always_on': False
        },
        'analytics': {
            'name': 'Analytics Cookies',
            'description': 'Help us improve our website',
            'always_on': False
        },
        'marketing': {
            'name': 'Marketing Cookies',
            'description': 'Track your activity for marketing',
            'always_on': False
        }
    }
    
    @classmethod
    def get_cookie_settings(cls, request):
        """Get current cookie settings from request"""
        consent = request.COOKIES.get('cookie_consent', '{}')
        
        try:
            import json
            settings = json.loads(consent)
        except:
            settings = {}
        
        return settings
    
    @classmethod
    def check_category(cls, request, category):
        """Check if cookie category is allowed"""
        if category == 'essential':
            return True
        
        settings = cls.get_cookie_settings(request)
        return settings.get(category, False)
    
    @classmethod
    def get_cookie_script(cls, category):
        """Get cookie script for category"""
        scripts = {
            'analytics': '''
                <!-- Google Analytics -->
                <script async src="https://www.googletagmanager.com/gtag/js?id=UA-XXXXX-Y"></script>
                <script>
                    window.dataLayer = window.dataLayer || [];
                    function gtag(){dataLayer.push(arguments);}
                    gtag('js', new Date());
                    gtag('config', 'UA-XXXXX-Y');
                </script>
            ''',
            'marketing': '''
                <!-- Facebook Pixel -->
                <script>
                    !function(f,b,e,v,n,t,s)
                    {if(f.fbq)return;n=f.fbq=function(){n.callMethod?
                    n.callMethod.apply(n,arguments):n.queue.push(arguments)};
                    if(!f._fbq)f._fbq=n;n.push=n;n.loaded=!0;n.version='2.0';
                    n.queue=[];t=b.createElement(e);t.async=!0;
                    t.src=v;s=b.getElementsByTagName(e)[0];
                    s.parentNode.insertBefore(t,s)}(window, document,'script',
                    'https://connect.facebook.net/en_US/fbevents.js');
                    fbq('init', 'YOUR_PIXEL_ID');
                    fbq('track', 'PageView');
                </script>
            '''
        }
        return scripts.get(category, '')