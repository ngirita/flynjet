# apps/core/context_processors.py - CLEAN VERSION

from django.utils import timezone
from .models import (
    SiteSettings, Notification, OfficeLocation, CompanyContact, 
    PaymentMethodConfig, SocialLink
)


def site_settings(request):
    """Add site settings to all templates"""
    try:
        settings = SiteSettings.get_settings()
    except:
        settings = None
    
    return {
        'site_settings': settings,
        'current_year': timezone.now().year,
    }


def notifications(request):
    """Add user notifications to template context."""
    if request.user.is_authenticated:
        notifications = Notification.objects.filter(
            recipient=request.user,
            is_read=False
        ).order_by('-created_at')[:10]
        unread_count = notifications.count()
    else:
        notifications = []
        unread_count = 0
    
    return {
        'notifications': notifications,
        'unread_notifications_count': unread_count
    }


def current_year(request):
    """Add current year to template context."""
    return {
        'current_year': timezone.now().year
    }


def analytics(request):
    """Add analytics tracking IDs to template context."""
    settings = SiteSettings.get_settings()
    return {
        'google_analytics_id': settings.google_analytics_id,
        'facebook_pixel_id': settings.facebook_pixel_id
    }


def footer_data(request):
    """Add footer data (offices, contacts) to all templates"""
    offices = OfficeLocation.objects.filter(is_active=True)
    contacts = CompanyContact.objects.filter(is_active=True)
    
    # Get phone and WhatsApp specifically
    phone = contacts.filter(contact_type='phone', is_primary=True).first()
    if not phone:
        phone = contacts.filter(contact_type='phone').first()
    
    whatsapp = contacts.filter(contact_type='whatsapp', is_primary=True).first()
    if not whatsapp:
        whatsapp = contacts.filter(contact_type='whatsapp').first()
    
    email = contacts.filter(contact_type='email', is_primary=True).first()
    if not email:
        email = contacts.filter(contact_type='email').first()
    
    return {
        'footer_offices': offices,
        'footer_contacts': contacts,
        'footer_phone': phone,
        'footer_whatsapp': whatsapp,
        'footer_email': email,
    }


def payment_methods(request):
    """Add payment methods to all templates"""
    # For normal users, show only enabled methods
    if not request.user.is_staff:
        methods = PaymentMethodConfig.objects.filter(is_enabled=True, is_visible=True).order_by('sort_order')
    else:
        # For admin/staff, show all methods for debugging
        methods = PaymentMethodConfig.objects.all().order_by('sort_order')
    
    # Add status flags for each method
    for method in methods:
        method.is_available = method.is_enabled and not method.is_maintenance
        method.status_message = method.maintenance_message if method.is_maintenance else ''
    
    return {
        'payment_methods': methods,
    }


def social_links(request):
    """Add social media links to all templates"""
    links = SocialLink.objects.filter(is_active=True).order_by('sort_order')
    
    # Prepare links with tracking URLs
    for link in links:
        link.tracking_url = link.get_full_url_with_tracking()
    
    return {
        'social_links': links,
    }