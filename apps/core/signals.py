# apps/core/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.urls import reverse
from django.utils import timezone

from .models import AdminNotification


def create_admin_notification(notification_type, title, message, link='', source_model='', source_id=''):
    """Helper function to create admin notification"""
    return AdminNotification.objects.create(
        notification_type=notification_type,
        title=title,
        message=message,
        link=link,
        source_model=source_model,
        source_id=str(source_id) if source_id else ''
    )


# ===== BOOKING SIGNALS =====
@receiver(post_save, sender='bookings.Booking')
def booking_created_notification(sender, instance, created, **kwargs):
    """Create notification when a new booking is made"""
    if created:
        route = f"{instance.departure_airport} to {instance.arrival_airport}"
        customer_name = instance.user.get_full_name() or instance.user.email
        
        create_admin_notification(
            notification_type='booking',
            title=f"New Booking: {instance.booking_reference}",
            message=f"{customer_name} booked {route} for {instance.departure_datetime.strftime('%Y-%m-%d')}",
            link=reverse('admin:bookings_booking_change', args=[instance.id]),
            source_model='booking',
            source_id=instance.id
        )


# ===== PAYMENT SIGNALS =====
@receiver(post_save, sender='payments.Payment')
def payment_created_notification(sender, instance, created, **kwargs):
    """Create notification when a payment is made"""
    if created:
        customer_name = instance.user.get_full_name() or instance.user.email
        booking_ref = instance.booking.booking_reference if instance.booking else 'N/A'
        
        create_admin_notification(
            notification_type='payment',
            title=f"New Payment: ${instance.amount_usd:,.2f}",
            message=f"{customer_name} paid ${instance.amount_usd:,.2f} for booking {booking_ref} via {instance.get_payment_method_display()}",
            link=reverse('admin:payments_payment_change', args=[instance.id]),
            source_model='payment',
            source_id=instance.id
        )


# ===== DISPUTE SIGNALS =====
@receiver(post_save, sender='disputes.Dispute')
def dispute_created_notification(sender, instance, created, **kwargs):
    """Create notification when a dispute is filed"""
    if created:
        customer_name = instance.user.get_full_name() or instance.user.email
        booking_ref = instance.booking.booking_reference if instance.booking else 'N/A'
        
        create_admin_notification(
            notification_type='dispute',
            title=f"New Dispute: {instance.dispute_number}",
            message=f"{customer_name} filed a {instance.get_dispute_type_display()} dispute for booking {booking_ref}",
            link=reverse('admin:disputes_dispute_change', args=[instance.id]),
            source_model='dispute',
            source_id=instance.id
        )


# ===== ENQUIRY SIGNALS =====
@receiver(post_save, sender='fleet.Enquiry')
def enquiry_created_notification(sender, instance, created, **kwargs):
    """Create notification when a new enquiry is submitted"""
    if created:
        customer_name = instance.get_full_name()
        route = f"{instance.departure_airport} to {instance.arrival_airport}"
        
        create_admin_notification(
            notification_type='enquiry',
            title=f"New Enquiry: {instance.enquiry_number}",
            message=f"{customer_name} enquired about flight from {route}",
            link=reverse('admin:fleet_enquiry_change', args=[instance.id]),
            source_model='enquiry',
            source_id=instance.id
        )


# ===== SUPPORT TICKET SIGNALS =====
@receiver(post_save, sender='core.SupportTicket')
def support_ticket_created_notification(sender, instance, created, **kwargs):
    """Create notification when a support ticket is created"""
    if created:
        customer_name = instance.user.get_full_name() or instance.user.email
        
        create_admin_notification(
            notification_type='support',
            title=f"New Support Ticket: {instance.ticket_number}",
            message=f"{customer_name} opened ticket: {instance.subject[:50]}",
            link=reverse('admin:core_supportticket_change', args=[instance.id]),
            source_model='support_ticket',
            source_id=instance.id
        )


# ===== REVIEW SIGNALS =====
@receiver(post_save, sender='reviews.Review')
def review_created_notification(sender, instance, created, **kwargs):
    """Create notification when a new review is submitted"""
    if created and instance.status == 'pending':
        customer_name = instance.user.get_full_name() or instance.user.email
        aircraft = instance.aircraft.model if instance.aircraft else 'N/A'
        
        create_admin_notification(
            notification_type='review',
            title=f"New Review: {instance.review_number}",
            message=f"{customer_name} rated {aircraft} {instance.overall_rating}/5 stars",
            link=reverse('admin:reviews_review_change', args=[instance.id]),
            source_model='review',
            source_id=instance.id
        )