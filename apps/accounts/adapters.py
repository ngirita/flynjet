from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib.auth import login
from django.urls import reverse
from django.shortcuts import redirect
from django.contrib import messages
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


class CustomAccountAdapter(DefaultAccountAdapter):
    """Custom account adapter for email 2FA and verification"""

    def login(self, request, user):
        """Custom login with 2FA check"""
        try:
            from .models import UserSecuritySettings
            
            # Check if 2FA is enabled
            try:
                security_settings = user.security_settings
                if security_settings.two_factor_enabled:
                    # Store user ID in session for 2FA verification
                    request.session['2fa_user_id'] = str(user.id)
                    request.session['2fa_next_url'] = request.GET.get('next', '/')
                    request.session['2fa_social_login'] = False
                    messages.info(request, 'Please enter your 2FA verification code.')
                    return redirect('accounts:2fa_verify')
            except UserSecuritySettings.DoesNotExist:
                pass
        except Exception as e:
            logger.error(f"Error in custom login adapter: {e}")
        
        # Normal login
        super().login(request, user)
        return redirect(self.get_login_redirect_url(request))

    def get_login_redirect_url(self, request):
        """Get login redirect URL"""
        next_url = request.GET.get('next')
        if next_url:
            return next_url
        return reverse('core:home')

    def is_open_for_signup(self, request):
        """Allow signup"""
        return True

    def send_confirmation_mail(self, request, emailconfirmation, signup):
        """Send confirmation email"""
        try:
            super().send_confirmation_mail(request, emailconfirmation, signup)
        except Exception as e:
            logger.error(f"Error sending confirmation email: {e}")


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    """Custom social account adapter for Google/Facebook login with 2FA"""

    def pre_social_login(self, request, sociallogin):
        """Before social login, check if user exists and handle 2FA"""
        try:
            from .models import User
            
            # Get email from social account
            email = sociallogin.account.extra_data.get('email')
            
            if email:
                try:
                    user = User.objects.get(email=email)
                    # Check if user has 2FA enabled
                    if user.security_settings.two_factor_enabled:
                        # Store user ID and social login info in session
                        request.session['2fa_user_id'] = str(user.id)
                        request.session['2fa_next_url'] = request.GET.get('next', '/')
                        request.session['2fa_social_login'] = True
                        request.session['2fa_social_provider'] = sociallogin.account.provider
                        messages.info(request, 'Please enter your 2FA verification code.')
                        raise Exception('2FA Required')
                except User.DoesNotExist:
                    pass
        except Exception as e:
            if str(e) == '2FA Required':
                raise
            logger.error(f"Error in pre_social_login: {e}")
        
        return super().pre_social_login(request, sociallogin)

    def save_user(self, request, sociallogin, form=None):
        """Save user from social login"""
        try:
            from .models import UserProfile, UserSecuritySettings, UserNotificationPreferences, LoginHistory
            
            user = super().save_user(request, sociallogin, form)
            
            # Set email as verified since it comes from social provider
            user.email_verified = True
            user.save()
            
            # Create profile if it doesn't exist
            UserProfile.objects.get_or_create(user=user)
            UserSecuritySettings.objects.get_or_create(user=user)
            UserNotificationPreferences.objects.get_or_create(user=user)
            
            # Update user details from social provider
            extra_data = sociallogin.account.extra_data
            
            if sociallogin.account.provider == 'google':
                user.first_name = extra_data.get('given_name', user.first_name)
                user.last_name = extra_data.get('family_name', user.last_name)
            elif sociallogin.account.provider == 'facebook':
                user.first_name = extra_data.get('first_name', user.first_name)
                user.last_name = extra_data.get('last_name', user.last_name)
            elif sociallogin.account.provider == 'linkedin_oauth2':
                user.first_name = extra_data.get('first-name', user.first_name)
                user.last_name = extra_data.get('last-name', user.last_name)
            
            user.save()
            
            # Log the social login
            LoginHistory.objects.create(
                user=user,
                login_type='social_login',
                ip_address=self.get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                success=True
            )
            
            return user
            
        except Exception as e:
            logger.error(f"Error saving social user: {e}")
            return super().save_user(request, sociallogin, form)

    def get_client_ip(self, request):
        """Get client IP from request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0]
        return request.META.get('REMOTE_ADDR')

    def populate_user(self, request, sociallogin, data):
        """Populate user with social data"""
        user = super().populate_user(request, sociallogin, data)
        
        # Set username from email if not set
        if not user.username and user.email:
            user.username = user.email.split('@')[0]
        
        return user