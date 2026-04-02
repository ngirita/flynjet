from django.urls import path
from django.conf import settings
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
    TokenBlacklistView
)
from apps.accounts.views import (
    RegisterView, LoginView, LogoutView,
    TwoFactorAuthView, TwoFactorSetupView, TwoFactorDisableView,
    PasswordResetRequestView, PasswordResetConfirmView,
    VerifyEmailView, ResendVerificationView
)

app_name = 'auth'

urlpatterns = [
    # JWT Token endpoints
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('token/verify/', TokenVerifyView.as_view(), name='token_verify'),
    path('token/blacklist/', TokenBlacklistView.as_view(), name='token_blacklist'),
    
    # Registration and Email Verification
    path('register/', RegisterView.as_view(), name='register'),
    path('verify-email/<str:token>/', VerifyEmailView.as_view(), name='verify_email'),
    path('resend-verification/', ResendVerificationView.as_view(), name='resend_verification'),
    
    # Login/Logout
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    
    # Two-Factor Authentication
    path('2fa/verify/', TwoFactorAuthView.as_view(), name='2fa_verify'),
    path('2fa/setup/', TwoFactorSetupView.as_view(), name='2fa_setup'),
    path('2fa/disable/', TwoFactorDisableView.as_view(), name='2fa_disable'),
    
    # Password Reset
    path('password-reset/', PasswordResetRequestView.as_view(), name='password_reset'),
    path('password-reset/confirm/', PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
]

# Check if allauth is actually enabled in INSTALLED_APPS
if 'allauth' in settings.INSTALLED_APPS:
    try:
        from allauth.socialaccount.providers.google.views import oauth2_login
        from allauth.socialaccount.providers.facebook.views import oauth2_login as facebook_login
        from allauth.socialaccount.providers.linkedin.views import oauth2_login as linkedin_login
        
        urlpatterns += [
            path('google/login/', oauth2_login, name='google_login'),
            path('facebook/login/', facebook_login, name='facebook_login'),
            path('linkedin/login/', linkedin_login, name='linkedin_login'),
        ]
    except ImportError:
        # Social auth providers not installed, skip
        pass
# If allauth is not in INSTALLED_APPS, don't even try to import