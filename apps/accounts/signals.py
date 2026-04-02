from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from django.contrib.auth.signals import user_logged_in, user_logged_out
from .models import User, UserProfile, UserSecuritySettings, UserNotificationPreferences, LoginHistory

@receiver(post_save, sender=User)
def create_user_related_models(sender, instance, created, **kwargs):
    """Create related models when a new user is created."""
    if created:
        UserProfile.objects.get_or_create(user=instance)
        UserSecuritySettings.objects.get_or_create(user=instance)
        UserNotificationPreferences.objects.get_or_create(user=instance)

@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    """Log user login."""
    user.record_login(request)

@receiver(user_logged_out)
def log_user_logout(sender, request, user, **kwargs):
    """Log user logout."""
    if user:
        LoginHistory.objects.create(
            user=user,
            ip_address=user.get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            login_type='logout'
        )

@receiver(pre_save, sender=User)
def track_password_change(sender, instance, **kwargs):
    """Track when password is changed."""
    if instance.pk:
        try:
            old_instance = User.objects.get(pk=instance.pk)
            if old_instance.password != instance.password:
                # Password has changed
                instance.password_changed_at = timezone.now()
                if hasattr(instance, 'security_settings'):
                    instance.security_settings.add_to_password_history(instance.password)
        except User.DoesNotExist:
            pass