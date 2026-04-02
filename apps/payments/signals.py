# apps/payments/signals.py - FIXED - ONLY ONE EMAIL

import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from .models import Payment
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from apps.bookings.models import Booking, BookingHistory
from apps.documents.models import GeneratedDocument

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Payment)
def handle_payment_status_change(sender, instance, created, **kwargs):
    """
    SINGLE HANDLER for payment status changes.
    Sends ONE email total - the confirmation with attachments.
    """
    # Only process when payment is completed
    if instance.status != 'completed':
        return
    
    if not instance.booking:
        logger.info(f"Payment {instance.transaction_id} completed but no booking associated")
        return
    
    # CRITICAL: Prevent duplicate processing
    if hasattr(instance, '_processed'):
        logger.info(f"Payment {instance.transaction_id} already processed, skipping")
        return
    
    # Mark as processed immediately
    instance._processed = True
    
    booking = instance.booking
    logger.info(f"Processing payment completion for booking {booking.booking_reference}")
    
    # ============ DETERMINE PAYMENT TYPE ============
    auto_confirm = instance.payment_method in ['card', 'paystack', 'stripe']
    
    # ============ 1. UPDATE BOOKING ============
    try:
        booking.amount_paid = instance.amount_usd
        booking.amount_due = booking.total_amount_usd - instance.amount_usd
        booking.payment_status = 'paid' if booking.amount_due <= 0 else 'partial'
        
        if auto_confirm and booking.amount_due <= 0:
            booking.status = 'paid'
            logger.info(f"Auto-confirming booking {booking.booking_reference}")
        else:
            booking.status = 'pending'
            logger.info(f"Booking {booking.booking_reference} awaiting admin confirmation")
        
        booking.save()
        logger.info(f"Booking {booking.booking_reference} updated - Paid: {booking.amount_paid}")
        
    except Exception as e:
        logger.error(f"Failed to update booking {booking.id}: {e}")
        return
    
    # ============ 2. CREATE BOOKING HISTORY ============
    try:
        if auto_confirm and booking.amount_due <= 0:
            new_status = 'paid'
            reason = f'Card payment completed via {instance.get_payment_method_display()}'
        else:
            new_status = 'pending'
            reason = f'{instance.get_payment_method_display()} payment initiated - awaiting admin confirmation'
        
        BookingHistory.objects.create(
            booking=booking,
            old_status='pending',
            new_status=new_status,
            changed_by=instance.user,
            reason=reason
        )
        logger.info(f"Booking history created for {booking.booking_reference}")
        
    except Exception as e:
        logger.error(f"Failed to create booking history: {e}")
    
    # ============ 3. GENERATE DOCUMENTS & SEND ONE EMAIL ============
    if auto_confirm and booking.amount_due <= 0:
        try:
            # Generate documents and send ONE confirmation email with attachments
            send_payment_confirmation_with_attachments(booking, instance)
            logger.info(f"Documents generated and email sent for booking {booking.booking_reference}")
        except Exception as e:
            logger.error(f"Failed to generate documents: {e}")
    else:
        # For bank/crypto, just send instructions email (already sent in PaymentCreateView)
        # Don't send another email here
        logger.info(f"Bank/crypto payment {instance.transaction_id} awaiting admin confirmation")
    
    # ============ 4. CREATE IN-APP NOTIFICATION (NO EMAIL) ============
    try:
        from apps.core.models import Notification
        
        if auto_confirm:
            title = 'Payment Successful'
            message = f'Your payment of ${instance.amount_usd:,.2f} for booking {booking.booking_reference} has been received. Invoice and ticket have been sent to your email.'
        else:
            title = 'Payment Received - Awaiting Confirmation'
            message = f'Your {instance.get_payment_method_display()} payment of ${instance.amount_usd:,.2f} for booking {booking.booking_reference} has been received and is pending confirmation. You will receive your documents once confirmed by admin.'
        
        Notification.objects.create(
            recipient=instance.user,
            notification_type='payment',
            title=title,
            message=message,
            related_object=instance
        )
        logger.info(f"Notification created for payment {instance.transaction_id}")
        
    except Exception as e:
        logger.error(f"Failed to create notification: {e}")


def send_payment_confirmation_with_attachments(booking, payment):
    """
    After payment: generate RECEIPT + TICKET and email them.
    Invoice was already sent with the contract BEFORE payment.
    """
    from io import BytesIO
    from django.template.loader import render_to_string
    from weasyprint import HTML
    from django.core.files.base import ContentFile

    documents = []

    # After payment: send RECEIPT and TICKET (not invoice - that was sent pre-payment)
    doc_types_to_generate = [
        ('receipt', 'invoices/standard.html'),   # Reuse standard template as receipt
        ('ticket', 'tickets/e_ticket.html'),
    ]

    for doc_type, template_name in doc_types_to_generate:
        try:
            # Get payment info
            payment_info = {
                'method': payment.get_payment_method_display(),
                'transaction_id': payment.transaction_id,
                'date': payment.payment_date,
                'amount': float(payment.amount_usd),
            }

            context = {
                'booking': {
                    'booking_reference': booking.booking_reference,
                    'departure_airport': booking.departure_airport,
                    'arrival_airport': booking.arrival_airport,
                    'departure_datetime': booking.departure_datetime,
                    'arrival_datetime': booking.arrival_datetime,
                    'passenger_count': booking.passenger_count,
                    'total_amount_usd': float(booking.total_amount_usd),
                    'amount_paid': float(booking.amount_paid),
                    'amount_due': float(booking.amount_due),
                    'status': booking.status,
                    'payment_status': booking.payment_status,
                    'flight_duration_hours': float(booking.flight_duration_hours) if booking.flight_duration_hours else 0,
                    'aircraft': {
                        'model': str(booking.aircraft.model),
                        'manufacturer': str(booking.aircraft.manufacturer.name),
                        'registration_number': str(booking.aircraft.registration_number),
                    }
                },
                'user': {
                    'first_name': booking.user.first_name,
                    'last_name': booking.user.last_name,
                    'email': booking.user.email,
                    'phone_number': str(getattr(booking.user, 'phone_number', '')),
                },
                'payment': payment_info,
                'document': {
                    'document_number': f"{'RCP' if doc_type == 'receipt' else 'TKT'}-{booking.booking_reference}-{timezone.now().strftime('%Y%m%d')}",
                    'created_at': timezone.now(),
                    'due_date': timezone.now(),
                    'subtotal_usd': float(booking.total_amount_usd - booking.tax_amount_usd),
                    'tax_rate': 10,
                    'tax_amount_usd': float(booking.tax_amount_usd),
                    'discount_amount_usd': float(booking.discount_amount_usd),
                    'total_usd': float(booking.total_amount_usd),
                    'items': [
                        {
                            'description': f'Charter Flight: {booking.departure_airport} → {booking.arrival_airport}',
                            'quantity': 1,
                            'unit_price_usd': float(booking.total_amount_usd),
                            'line_total_usd': float(booking.total_amount_usd),
                        }
                    ],
                    # Payment info for receipt template
                    'payment_method': payment_info['method'],
                    'payment_transaction_id': payment_info['transaction_id'],
                    'payment_date': payment_info['date'],
                    'status': 'paid',
                    'content_data': {
                        'payment_method': payment_info['method'],
                        'payment_transaction_id': payment_info['transaction_id'],
                        'payment_date': payment_info['date'].isoformat() if payment_info['date'] else None,
                        'status': 'paid',
                    }
                },
                'doc_type': doc_type,
                'is_receipt': doc_type == 'receipt',
                'company': {
                    'name': 'FlynJet Air and Logistics.',
                    'address': 'Jomo Kenyatta International Airport. Airport North Road, Embakasi, Nairobi Kenya',
                    'city': 'Nairobi',
                    'phone': '+254785651832',
                    'whatsapp': '+447393700477',
                    'email': 'info@flynjet.com',
                    'tax_id': '12-3456789',
                }
            }

            html_content = render_to_string(template_name, context)
            pdf_file = BytesIO()
            HTML(string=html_content).write_pdf(pdf_file)
            pdf_file.seek(0)

            document, created = GeneratedDocument.objects.update_or_create(
                user=booking.user,
                booking=booking,
                document_type=doc_type,
                defaults={
                    'title': f"{'Receipt' if doc_type == 'receipt' else 'Ticket'} - {booking.booking_reference}",
                    'content_data': {
                        'payment_method': payment_info['method'],
                        'payment_transaction_id': payment_info['transaction_id'],
                        'payment_date': payment_info['date'].isoformat() if payment_info['date'] else None,
                        'amount_paid': payment_info['amount'],
                        'status': 'paid',
                    },
                    'status': 'generated'
                }
            )

            filename = f"{doc_type}_{booking.booking_reference}.pdf"
            document.pdf_file.save(filename, ContentFile(pdf_file.getvalue()))
            documents.append(document)

            logger.info(f"Post-payment {doc_type} generated for booking {booking.booking_reference}")

        except Exception as e:
            logger.error(f"Failed to generate {doc_type} for booking {booking.id}: {e}")

    # Send ONE email with receipt + ticket
    if documents:
        send_single_confirmation_email(booking, booking.user, payment, documents)


def send_single_confirmation_email(booking, user, payment, documents):
    """Send ONE post-payment email: receipt + ticket attached"""
    subject = f"Payment Receipt & E-Ticket - Booking {booking.booking_reference}"

    context = {
        'booking': booking,
        'user': user,
        'payment': payment,
        'amount_paid': booking.amount_paid,
        'booking_reference': booking.booking_reference,
    }

    html_message = render_to_string('emails/payment_confirmation.html', context)
    plain_message = f"""
Dear {user.get_full_name() or user.email},

Your payment of ${booking.amount_paid:,.2f} for booking {booking.booking_reference} has been confirmed.

Attached to this email:
  ✓ Payment Receipt
  ✓ E-Ticket

Transaction ID: {payment.transaction_id}
Payment Method: {payment.get_payment_method_display()}

Thank you for choosing FlynJet!

Regards,
FlynJet Team
---
FlynJet Air and Logistics. | info@flynjet.com | +254785651832
"""

    email = EmailMultiAlternatives(
        subject=subject,
        body=plain_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email]
    )
    email.attach_alternative(html_message, "text/html")

    for doc in documents:
        if doc.pdf_file:
            label = 'Receipt' if doc.document_type == 'receipt' else 'ETicket'
            doc.pdf_file.seek(0)
            email.attach(
                filename=f"{label}_{booking.booking_reference}.pdf",
                content=doc.pdf_file.read(),
                mimetype='application/pdf'
            )

    try:
        email.send(fail_silently=False)
        logger.info(f"Post-payment email (receipt+ticket) sent to {user.email} for {booking.booking_reference}")
    except Exception as e:
        logger.error(f"Failed to send post-payment email: {e}")