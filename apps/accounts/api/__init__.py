# apps/accounts/api/__init__.py

# Import from views.py (which contains your web views)
from apps.accounts.views import (
    RegisterView,
    LoginView,
    LogoutView,
    TwoFactorAuthView,
    TwoFactorSetupView,
    TwoFactorDisableView,
    PasswordResetView,
    PasswordResetConfirmView,
    ProfileView,
    SecuritySettingsView,
    VerifyEmailView,
    ResendVerificationView,
    PasswordChangeView,
    PasswordResetRequestView,
    PasswordResetDoneView,
    PasswordResetCompleteView,
)

# Import from api.py (which contains your API views) - FIXED: import from the module, not from itself
from apps.accounts.api_views import (  # Changed from api to api_views
    UserViewSet,
    LoginHistoryViewSet,
)

from .auth_urls import urlpatterns as auth_urls

__all__ = [
    # Web views
    'RegisterView',
    'LoginView',
    'LogoutView',
    'TwoFactorAuthView',
    'TwoFactorSetupView',
    'TwoFactorDisableView',
    'PasswordResetView',
    'PasswordResetConfirmView',
    'ProfileView',
    'SecuritySettingsView',
    'VerifyEmailView',
    'ResendVerificationView',
    'PasswordChangeView',
    'PasswordResetRequestView',
    'PasswordResetDoneView',
    'PasswordResetCompleteView',
    
    # API views
    'UserViewSet',
    'LoginHistoryViewSet',
    
    # URLs
    'auth_urls',
]