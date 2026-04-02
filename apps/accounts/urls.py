from django.urls import path
from django.shortcuts import redirect
from . import views

app_name = 'accounts'

urlpatterns = [
    # Authentication
    path('register/', views.RegisterView.as_view(), name='register'),
    path('login/', views.LoginView.as_view(), name='login'),
    path('logout/', views.LogoutView.as_view(), name='logout'),
    path('admin-dashboard/', lambda request: redirect('admin:index'), name='admin_dashboard'),
    
    # Email Verification
    path('verify-email/<str:token>/', views.VerifyEmailView.as_view(), name='verify_email'),
    path('resend-verification/', views.ResendVerificationView.as_view(), name='resend_verification'),
    
    # OTP
    path('resend-otp/', views.ResendOTPView.as_view(), name='resend_otp'),  # ADD THIS LINE
    
    # Password Reset
    path('password-reset/', views.PasswordResetRequestView.as_view(), name='password_reset'),
    path('password-reset/done/', views.PasswordResetDoneView.as_view(), name='password_reset_done'),
    path('password-reset/<str:token>/', views.PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('password-reset/complete/', views.PasswordResetCompleteView.as_view(), name='password_reset_complete'),
    
    # Profile
    path('profile/', views.ProfileView.as_view(), name='profile'),
    path('profile/edit/', views.EditProfileView.as_view(), name='edit_profile'),
    path('profile/security/', views.SecuritySettingsView.as_view(), name='security_settings'),
    
    # Two Factor
    path('2fa/setup/', views.TwoFactorSetupView.as_view(), name='2fa_setup'),
    path('2fa/verify/', views.TwoFactorAuthView.as_view(), name='2fa_verify'),
    path('2fa/disable/', views.TwoFactorDisableView.as_view(), name='2fa_disable'),
]