from celery import shared_task
from django.utils import timezone
from django.core.mail import send_mail
from .models import Booking
import logging

logger = logging.getLogger(__name__)

@shared_task
def check_expired_bookings():
    """Check and update expired bookings."""
    expired_drafts = Booking.objects.filter(
        status='draft',
        created_at__lt=timezone.now() - timezone.timedelta(hours=24)
    )
    count = expired_drafts.update(status='cancelled')
    logger.info(f"Cancelled {count} expired draft bookings")
    return count

@shared_task
def send_booking_reminders():
    """Send reminders for upcoming bookings."""
    upcoming_bookings = Booking.objects.filter(
        status='confirmed',
        departure_datetime__gte=timezone.now() + timezone.timedelta(days=1),
        departure_datetime__lte=timezone.now() + timezone.timedelta(days=2)
    )
    
    for booking in upcoming_bookings:
        send_booking_reminder_email.delay(booking.id)
    
    return upcoming_bookings.count()

@shared_task
def send_booking_reminder_email(booking_id):
    """Send reminder email for specific booking."""
    try:
        booking = Booking.objects.get(id=booking_id)
        subject = f"Booking Reminder - {booking.booking_reference}"
        message = f"Your flight is tomorrow at {booking.departure_datetime}"
        send_mail(
            subject,
            message,
            'flynjetair@gmail.com',
            [booking.user.email],
            fail_silently=False,
        )
        logger.info(f"Reminder sent for booking {booking_id}")
    except Booking.DoesNotExist:
        logger.error(f"Booking {booking_id} not found")

@shared_task
def generate_invoice(booking_id):
    """Generate invoice for booking."""
    from .utils import generate_invoice_pdf
    try:
        booking = Booking.objects.get(id=booking_id)
        invoice = booking.invoices.first()
        if invoice and not invoice.pdf_file:
            pdf_file = generate_invoice_pdf(invoice)
            invoice.pdf_file.save(f"invoice_{invoice.invoice_number}.pdf", pdf_file)
            logger.info(f"Invoice generated for booking {booking_id}")
    except Booking.DoesNotExist:
        logger.error(f"Booking {booking_id} not found")

@shared_task
def cleanup_old_drafts():
    """Delete old draft bookings."""
    old_drafts = Booking.objects.filter(
        status='draft',
        created_at__lt=timezone.now() - timezone.timedelta(days=7)
    )
    count = old_drafts.delete()[0]
    logger.info(f"Deleted {count} old draft bookings")
    return count