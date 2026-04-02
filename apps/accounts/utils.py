import secrets
import string
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone
from .models import EmailVerification, PasswordReset

def generate_verification_token(user):
    """Generate email verification token."""
    token = secrets.token_urlsafe(32)
    EmailVerification.objects.create(
        user=user,
        token=token,
        expires_at=timezone.now() + timezone.timedelta(hours=24)
    )
    return token

def generate_password_reset_token(user):
    """Generate password reset token."""
    token = secrets.token_urlsafe(32)
    PasswordReset.objects.create(
        user=user,
        token=token,
        expires_at=timezone.now() + timezone.timedelta(hours=1)
    )
    return token

def send_verification_email(user, request):
    """Send email verification email."""
    token = generate_verification_token(user)
    verification_url = f"{settings.SITE_URL}/accounts/verify-email/{token}/"
    
    context = {
        'user': user,
        'verification_url': verification_url
    }
    
    html_message = render_to_string('accounts/emails/verify_email.html', context)
    plain_message = render_to_string('accounts/emails/verify_email.txt', context)
    
    send_mail(
        'Verify your email - FlynJet',
        plain_message,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        html_message=html_message,
        fail_silently=False,
    )

def send_welcome_email(user):
    """Send welcome email."""
    context = {
        'user': user,
        'login_url': f"{settings.SITE_URL}/accounts/login/"
    }
    
    html_message = render_to_string('accounts/emails/welcome.html', context)
    plain_message = render_to_string('accounts/emails/welcome.txt', context)
    
    send_mail(
        'Welcome to FlynJet!',
        plain_message,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        html_message=html_message,
        fail_silently=False,
    )

def generate_username_from_email(email):
    """Generate username from email address."""
    username = email.split('@')[0]
    # Ensure uniqueness
    from .models import User
    base_username = username
    counter = 1
    while User.objects.filter(username=username).exists():
        username = f"{base_username}{counter}"
        counter += 1
    return username

def generate_secure_password(length=16):
    """Generate a secure random password."""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    password = ''.join(secrets.choice(alphabet) for _ in range(length))
    return password