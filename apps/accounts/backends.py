from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.db.models import Q

User = get_user_model()

class EmailOrUsernameBackend(ModelBackend):
    """
    Authentication backend that allows login with either email or username.
    """
    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None:
            username = kwargs.get('email')
        
        if username is None or password is None:
            return None
        
        try:
            # Try to find user by email or username
            user = User.objects.get(
                Q(email__iexact=username) | 
                Q(username__iexact=username)
            )
        except User.DoesNotExist:
            return None
        
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        
        return None

class CaseInsensitiveEmailBackend(ModelBackend):
    """
    Authentication backend that uses case-insensitive email lookup.
    """
    def authenticate(self, request, email=None, password=None, **kwargs):
        if email is None or password is None:
            return None
        
        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            return None
        
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        
        return None

class TwoFactorBackend(ModelBackend):
    """
    Authentication backend that checks for 2FA requirement.
    """
    def authenticate(self, request, email=None, password=None, **kwargs):
        if email is None or password is None:
            return None
        
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return None
        
        if user.check_password(password) and self.user_can_authenticate(user):
            # Check if 2FA is required
            if hasattr(user, 'security_settings') and user.security_settings.two_factor_enabled:
                # Store user id in session for 2FA verification
                request.session['2fa_user_id'] = str(user.id)
                return None  # Don't authenticate yet, need 2FA
            return user
        
        return None