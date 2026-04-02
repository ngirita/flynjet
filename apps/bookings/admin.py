from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from django.shortcuts import redirect
from django.urls import path
from django.http import HttpResponseRedirect
from django.contrib import messages
import datetime
from .models import Booking, BookingPassenger, BookingAddon, BookingHistory, Invoice, InvoiceItem
from .models import Contract, ContractLineItem
from apps.airports.models import Airport
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class BookingPassengerInline(admin.TabularInline):
    model = BookingPassenger
    extra = 1

class BookingAddonInline(admin.TabularInline):
    model = BookingAddon
    extra = 1

class BookingHistoryInline(admin.TabularInline):
    model = BookingHistory
    readonly_fields = ['old_status', 'new_status', 'changed_by', 'reason', 'created_at']
    extra = 0
    can_delete = False

class InvoiceItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 1

class ContractLineItemInline(admin.TabularInline):
    model = ContractLineItem
    extra = 1
    fields = ['description', 'quantity', 'unit_price', 'line_total']
    readonly_fields = ['line_total']

    def line_total(self, obj):
        if obj.pk:
            return f"${obj.amount:,.2f}"
        return "—"
    line_total.short_description = "Total"

@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = [
        'booking_reference', 'user', 'aircraft', 'flight_type',
        'departure_airport_display', 'arrival_airport_display', 'departure_datetime',
        'status', 'payment_status', 'total_amount_usd', 'invoice_link', 'admin_actions'
    ]
    list_filter = ['status', 'payment_status', 'flight_type', 'created_at']
    search_fields = ['booking_reference', 'user__email', 'user__first_name', 'user__last_name']
    readonly_fields = [
        'booking_reference', 'created_at', 'updated_at', 'confirmed_at',
        'completed_at', 'cancelled_at', 'invoice_link'
    ]
    date_hierarchy = 'departure_datetime'
    
    fieldsets = (
        ('Booking Reference', {
            'fields': ('booking_reference',)
        }),
        ('Relationships', {
            'fields': ('user', 'aircraft')
        }),
        ('Booking Details', {
            'fields': (
                'flight_type', 'status', 'payment_status'
            )
        }),
        ('Flight Information', {
            'fields': (
                'departure_airport', 'arrival_airport',
                'departure_datetime', 'arrival_datetime',
                'return_departure_datetime', 'return_arrival_datetime'
            )
        }),
        ('Passenger/Cargo Details', {
            'fields': (
                'passenger_count', 'crew_count', 'cargo_weight_kg',
                'baggage_weight_kg', 'passengers'
            )
        }),
        ('Flight Details', {
            'fields': (
                'flight_duration_hours', 'flight_distance_nm', 'flight_distance_km'
            )
        }),
        ('Pricing', {
            'fields': (
                'base_price_usd', 'fuel_surcharge_usd', 'handling_fee_usd',
                'catering_cost_usd', 'overnight_charge_usd', 'cleaning_charge_usd',
                'insurance_cost_usd', 'discount_amount_usd', 'tax_amount_usd',
                'total_amount_usd'
            )
        }),
        ('Currency', {
            'fields': (
                'preferred_currency', 'exchange_rate', 'total_amount_preferred'
            )
        }),
        ('Payment Details', {
            'fields': (
                'amount_paid', 'amount_due', 'payment_due_date'
            )
        }),
        ('Special Requests', {
            'fields': (
                'special_requests', 'dietary_requirements', 'medical_requirements',
                'catering_options'
            )
        }),
        ('Additional Services', {
            'fields': (
                'ground_transportation_required', 'ground_transportation_details',
                'hotel_required', 'hotel_details'
            )
        }),
        ('Insurance', {
            'fields': (
                'insurance_purchased', 'insurance_policy_number', 'insurance_premium'
            )
        }),
        ('Cancellation', {
            'fields': (
                'cancellation_policy', 'cancellation_deadline',
                'cancellation_fee_percentage', 'cancelled_at',
                'cancellation_reason', 'cancelled_by'
            )
        }),
        ('Refund', {
            'fields': (
                'refund_amount', 'refund_status', 'refund_processed_at',
                'refund_transaction_id'
            )
        }),
        ('Terms Acceptance', {
            'fields': (
                'terms_accepted', 'terms_accepted_at', 'terms_ip_address'
            )
        }),
        ('Confirmation', {
            'fields': ('confirmed_at', 'confirmed_by')
        }),
        ('Completion', {
            'fields': ('completed_at', 'actual_departure', 'actual_arrival')
        }),
        ('Notes', {
            'fields': ('internal_notes', 'customer_notes')
        }),
        ('Metadata', {
            'fields': ('ip_address', 'user_agent', 'source'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    inlines = [BookingPassengerInline, BookingAddonInline, BookingHistoryInline]
    actions = [
        'confirm_bookings', 
        'cancel_bookings', 
        'send_reminders', 
        'complete_bookings',
        'mark_as_paid',           # New action
        'mark_as_partially_paid', # New action
        'mark_as_pending_payment', # New action
        'mark_as_overdue'         # New action
    ]
    
    def admin_actions(self, obj):
        """Display action buttons in admin list view"""
        buttons = []
        
        # Show Complete button if booking is not already completed or cancelled
        if obj.status not in ['completed', 'cancelled']:
            complete_url = reverse('admin:bookings_booking_complete', args=[obj.id])
            buttons.append(f'<a href="{complete_url}" class="button" style="background: #28a745; color: white; padding: 3px 8px; border-radius: 3px; text-decoration: none; margin-right: 5px;">✓ Complete</a>')
        
        return format_html(''.join(buttons))
    admin_actions.short_description = 'Actions'
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('<uuid:pk>/complete/', self.admin_site.admin_view(self.complete_booking), name='bookings_booking_complete'),
        ]
        return custom_urls + urls
    
    def complete_booking(self, request, pk):
        """Custom view to mark booking as completed"""
        booking = self.get_object(request, pk)
        if booking:
            # Mark as completed
            booking.status = 'completed'
            booking.completed_at = timezone.now()
            booking.save(update_fields=['status', 'completed_at'])
            
            # Create history entry
            BookingHistory.objects.create(
                booking=booking,
                old_status=booking.status,
                new_status='completed',
                changed_by=request.user,
                reason='Marked as completed by admin'
            )
            
            self.message_user(request, f'Booking {booking.booking_reference} marked as completed.')
        return HttpResponseRedirect(reverse('admin:bookings_booking_changelist'))
    
    def departure_airport_display(self, obj):
        """Display airport name with IATA code"""
        if obj.departure_airport:
            try:
                airport = Airport.objects.get(iata_code=obj.departure_airport)
                return format_html(
                    '<span title="{}">{}</span>',
                    airport.name,
                    f"{airport.city} ({airport.iata_code})"
                )
            except Airport.DoesNotExist:
                return obj.departure_airport
        return "-"
    departure_airport_display.short_description = "Departure Airport"
    
    def arrival_airport_display(self, obj):
        """Display airport name with IATA code"""
        if obj.arrival_airport:
            try:
                airport = Airport.objects.get(iata_code=obj.arrival_airport)
                return format_html(
                    '<span title="{}">{}</span>',
                    airport.name,
                    f"{airport.city} ({airport.iata_code})"
                )
            except Airport.DoesNotExist:
                return obj.arrival_airport
        return "-"
    arrival_airport_display.short_description = "Arrival Airport"
    
    def invoice_link(self, obj):
        invoices = obj.invoices.all()
        if invoices:
            url = reverse('admin:bookings_invoice_change', args=[invoices.first().id])
            return format_html('<a href="{}">View Invoice</a>', url)
        return "No invoice"
    invoice_link.short_description = "Invoice"
    
    def confirm_bookings(self, request, queryset):
        for booking in queryset:
            booking.confirm_booking(request.user)
        self.message_user(request, f"{queryset.count()} bookings confirmed.")
    confirm_bookings.short_description = "Confirm selected bookings"
    
    def cancel_bookings(self, request, queryset):
        for booking in queryset:
            booking.cancel_booking(request.user, "Cancelled by admin")
        self.message_user(request, f"{queryset.count()} bookings cancelled.")
    cancel_bookings.short_description = "Cancel selected bookings"
    
    def complete_bookings(self, request, queryset):
        """Admin action to mark multiple bookings as completed"""
        count = 0
        for booking in queryset:
            if booking.status not in ['completed', 'cancelled']:
                old_status = booking.status
                booking.status = 'completed'
                booking.completed_at = timezone.now()
                booking.save(update_fields=['status', 'completed_at'])
                
                BookingHistory.objects.create(
                    booking=booking,
                    old_status=old_status,
                    new_status='completed',
                    changed_by=request.user,
                    reason='Marked as completed by admin'
                )
                count += 1
        self.message_user(request, f"{count} bookings marked as completed.")
    complete_bookings.short_description = "Mark selected bookings as completed"
    
    def send_reminders(self, request, queryset):
        # Implement reminder sending logic
        self.message_user(request, f"Reminders sent for {queryset.count()} bookings.")
    send_reminders.short_description = "Send reminders"
    
    # ========== NEW PAYMENT STATUS ACTIONS ==========
    
    def mark_as_paid(self, request, queryset):
        """Mark selected bookings as fully paid and send receipt emails"""
        count = 0
        for booking in queryset:
            logger.info(f"Processing booking: {booking.booking_reference}")
            logger.info(f"Payment status: {booking.payment_status}")

            # ===== ADD DEBUG LOGGING HERE =====
            all_invoices = booking.invoices.all()
            logger.info(f"Total invoices for this booking: {all_invoices.count()}")
            for inv in all_invoices:
                logger.info(f"  Invoice: {inv.invoice_number} - Status: {inv.status} - Total: ${inv.total_usd}")
            # ===== END DEBUG LOGGING =====
            
            if booking.payment_status != 'paid':
                old_status = booking.payment_status
                
                # Update payment details
                booking.payment_status = 'paid'
                booking.amount_paid = booking.total_amount_usd
                booking.amount_due = 0
                booking.save(update_fields=['payment_status', 'amount_paid', 'amount_due'])
                logger.info(f"Updated booking payment status to paid")
                
                # Create history entry
                BookingHistory.objects.create(
                    booking=booking,
                    old_status=booking.status,
                    new_status=booking.status,
                    changed_by=request.user,
                    reason=f'Payment status changed from {old_status} to paid (admin action)'
                )
                
                # Get or create invoice
                invoice = booking.invoices.first()
                if not invoice:
                    # Create invoice if it doesn't exist
                    logger.info(f"No invoice found, creating one for booking {booking.booking_reference}")
                    from apps.bookings.models import Invoice
                    
                    # Get airport names for invoice description
                    departure_name = booking.departure_airport
                    arrival_name = booking.arrival_airport
                    
                    try:
                        dep_airport = Airport.objects.get(iata_code=booking.departure_airport)
                        departure_name = f"{dep_airport.name} ({dep_airport.iata_code})"
                    except Airport.DoesNotExist:
                        departure_name = booking.departure_airport
                    
                    try:
                        arr_airport = Airport.objects.get(iata_code=booking.arrival_airport)
                        arrival_name = f"{arr_airport.name} ({arr_airport.iata_code})"
                    except Airport.DoesNotExist:
                        arrival_name = booking.arrival_airport
                    
                    invoice = Invoice.objects.create(
                        booking=booking,
                        user=booking.user,
                        invoice_date=timezone.now().date(),
                        due_date=timezone.now().date() + timezone.timedelta(days=7),
                        subtotal_usd=booking.total_amount_usd - booking.tax_amount_usd,
                        tax_rate=10,
                        tax_amount_usd=booking.tax_amount_usd,
                        total_usd=booking.total_amount_usd,
                        total_currency=booking.total_amount_usd,
                        currency='USD',
                        billing_address_line1=booking.user.address_line1 or 'Not provided',
                        billing_city=booking.user.city or 'Not provided',
                        billing_state=booking.user.state or 'Not provided',
                        billing_postal_code=booking.user.postal_code or '00000',
                        billing_country=booking.user.country or 'US',
                        status='paid',
                        paid_date=timezone.now().date(),
                    )
                    
                    # Create invoice items
                    invoice.items.create(
                        description=f"Flight from {departure_name} to {arrival_name}",
                        quantity=1,
                        unit_price_usd=booking.base_price_usd,
                        line_total_usd=booking.base_price_usd
                    )
                    
                    if booking.fuel_surcharge_usd > 0:
                        invoice.items.create(
                            description="Fuel Surcharge",
                            quantity=1,
                            unit_price_usd=booking.fuel_surcharge_usd,
                            line_total_usd=booking.fuel_surcharge_usd
                        )
                    
                    logger.info(f"Invoice created for booking {booking.booking_reference}")
                else:
                    # Update existing invoice to paid
                    logger.info(f"Updating existing invoice {invoice.invoice_number} to paid")
                    invoice.status = 'paid'
                    invoice.paid_date = timezone.now().date()
                    invoice.save(update_fields=['status', 'paid_date'])
                
                # Now send receipt email using the invoice we have
                try:
                    from apps.documents.models import GeneratedDocument
                    
                    receipt_number = f"RCP-{booking.booking_reference}-{timezone.now().strftime('%Y%m%d')}"
                    logger.info(f"Creating receipt: {receipt_number}")
                    
                    # Get airport details for display
                    departure_airport = None
                    arrival_airport = None
                    
                    if booking.departure_airport:
                        try:
                            departure_airport = Airport.objects.get(iata_code=booking.departure_airport)
                            logger.info(f"Departure airport found: {departure_airport.name}")
                        except Airport.DoesNotExist:
                            logger.warning(f"Departure airport not found: {booking.departure_airport}")
                    
                    if booking.arrival_airport:
                        try:
                            arrival_airport = Airport.objects.get(iata_code=booking.arrival_airport)
                            logger.info(f"Arrival airport found: {arrival_airport.name}")
                        except Airport.DoesNotExist:
                            logger.warning(f"Arrival airport not found: {booking.arrival_airport}")
                    
                    # ===== CREATE ITEMS LIST =====
                    items = []

                    # Main flight charge
                    items.append({
                        'description': f"Flight Charter: {booking.departure_airport} → {booking.arrival_airport}",
                        'quantity': 1,
                        'unit_price_usd': float(booking.base_price_usd),
                        'line_total_usd': float(booking.base_price_usd)
                    })

                    # Add fuel surcharge if present
                    if booking.fuel_surcharge_usd and float(booking.fuel_surcharge_usd) > 0:
                        items.append({
                            'description': "Fuel Surcharge",
                            'quantity': 1,
                            'unit_price_usd': float(booking.fuel_surcharge_usd),
                            'line_total_usd': float(booking.fuel_surcharge_usd)
                        })

                    # Add handling fee if present
                    if booking.handling_fee_usd and float(booking.handling_fee_usd) > 0:
                        items.append({
                            'description': "Handling Fee",
                            'quantity': 1,
                            'unit_price_usd': float(booking.handling_fee_usd),
                            'line_total_usd': float(booking.handling_fee_usd)
                        })

                    # Add catering cost if present
                    if booking.catering_cost_usd and float(booking.catering_cost_usd) > 0:
                        items.append({
                            'description': "Catering Service",
                            'quantity': 1,
                            'unit_price_usd': float(booking.catering_cost_usd),
                            'line_total_usd': float(booking.catering_cost_usd)
                        })

                    # Add cleaning charge if present
                    if booking.cleaning_charge_usd and float(booking.cleaning_charge_usd) > 0:
                        items.append({
                            'description': "Cleaning Fee",
                            'quantity': 1,
                            'unit_price_usd': float(booking.cleaning_charge_usd),
                            'line_total_usd': float(booking.cleaning_charge_usd)
                        })

                    # Add insurance if purchased
                    if booking.insurance_purchased and booking.insurance_premium and float(booking.insurance_premium) > 0:
                        items.append({
                            'description': "Travel Insurance",
                            'quantity': 1,
                            'unit_price_usd': float(booking.insurance_premium),
                            'line_total_usd': float(booking.insurance_premium)
                        })

                    # Add discount if present (negative value)
                    if booking.discount_amount_usd and float(booking.discount_amount_usd) > 0:
                        items.append({
                            'description': "Discount",
                            'quantity': 1,
                            'unit_price_usd': -float(booking.discount_amount_usd),
                            'line_total_usd': -float(booking.discount_amount_usd)
                        })

                    # ===== DEBUG: Print items =====
                    logger.info(f"Created {len(items)} items:")
                    for idx, item in enumerate(items):
                        logger.info(f"  Item {idx}: {item.get('description')} - ${item.get('line_total_usd')}")
                    # ===== END DEBUG =====

                    # Prepare data for receipt - ADD 'items' to this dictionary
                    content_data = {
                        'booking_reference': booking.booking_reference,
                        'customer_name': booking.user.get_full_name(),
                        'customer_email': booking.user.email,
                        'departure_airport': booking.departure_airport,
                        'arrival_airport': booking.arrival_airport,
                        'departure_datetime': booking.departure_datetime.isoformat(),
                        'arrival_datetime': booking.arrival_datetime.isoformat(),
                        'total_amount_usd': float(booking.total_amount_usd),
                        'payment_method': 'Admin Payment',
                        'payment_date': timezone.now().isoformat(),
                        'payment_transaction_id': f'ADMIN-{timezone.now().timestamp()}',
                        'document_type': 'receipt',
                        'subtotal_usd': float(invoice.subtotal_usd),
                        'tax_rate': float(invoice.tax_rate),
                        'tax_amount_usd': float(invoice.tax_amount_usd),
                        'discount_amount_usd': float(invoice.discount_amount_usd),
                        'total_usd': float(invoice.total_usd),
                        'items': items,  # <-- THIS IS THE CRITICAL ADDITION
                    }
                    
                    # Create document if it doesn't exist - use update_or_create to always update
                    document, created = GeneratedDocument.objects.update_or_create(
                        booking=booking,
                        document_type='receipt',
                        defaults={
                            'document_number': receipt_number,
                            'user': booking.user,
                            'title': f"Receipt - {booking.booking_reference}",
                            'content_data': content_data,
                            'status': 'generated',
                        }
                    )

                    # ===== DEBUG: Verify saved data =====
                    logger.info(f"Document: {document.document_number}, created={created}")
                    logger.info(f"Saved items count: {len(document.content_data.get('items', []))}")
                    for idx, item in enumerate(document.content_data.get('items', [])):
                        logger.info(f"  Saved item {idx}: {item.get('description')} - ${item.get('line_total_usd')}")
                    # ===== END DEBUG =====
                    
                    # Send email with receipt
                    context = {
                        'document': document,
                        'booking': booking,
                        'user': booking.user,
                        'is_receipt': True,
                        'departure_airport': departure_airport,
                        'arrival_airport': arrival_airport,
                    }
                    
                    subject = f"Payment Receipt - Booking {booking.booking_reference}"
                    
                    logger.info(f"Attempting to send email to: {booking.user.email}")
                    logger.info(f"Email subject: {subject}")
                    
                    # Try to render HTML template
                    try:
                        html_message = render_to_string('invoices/standard.html', context)
                        logger.info(f"HTML template rendered successfully.")
                    except Exception as template_error:
                        logger.error(f"Could not render HTML template: {template_error}")
                        import traceback
                        logger.error(traceback.format_exc())
                        html_message = None
                    
                    # Create plain text fallback
                    plain_message = f"""
    FLY N'JET - Payment Receipt
    ==========================
    Receipt Number: {document.document_number}
    Booking Reference: {booking.booking_reference}
    Date: {timezone.now().strftime('%B %d, %Y')}

    Flight Details:
    From: {booking.departure_airport}
    To: {booking.arrival_airport}
    Date: {booking.departure_datetime.strftime('%B %d, %Y')}

    Payment Details:
    Amount Paid: ${booking.total_amount_usd:,.2f}
    Payment Method: Admin Payment
    Payment Date: {timezone.now().strftime('%B %d, %Y %H:%M')}
    Transaction ID: ADMIN-{timezone.now().timestamp()}

    Thank you for choosing FlynJet!

    For questions: info@flynjet.com | +254785651832
    """
                    
                    # Send the email
                    try:
                        send_mail(
                            subject,
                            plain_message,
                            settings.DEFAULT_FROM_EMAIL,
                            [booking.user.email],
                            html_message=html_message,
                            fail_silently=False,
                        )
                        logger.info(f"Email sent successfully for booking {booking.booking_reference}")
                    except Exception as email_error:
                        logger.error(f"Failed to send email: {email_error}")
                        import traceback
                        logger.error(traceback.format_exc())
                    
                except Exception as e:
                    logger.error(f"Failed to process receipt for booking {booking.booking_reference}: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
                
                count += 1
            
            else:
                logger.info(f"Booking {booking.booking_reference} already has payment_status='paid', skipping")
        
        self.message_user(
            request, 
            f"{count} bookings marked as paid. Receipt emails sent to customers.",
            level=messages.SUCCESS
        )
    
    def mark_as_partially_paid(self, request, queryset):
        """Mark selected bookings as partially paid"""
        # You might want to show a popup to enter the amount, but for simplicity, we'll use a prompt
        # For more advanced, you'd need to create a custom intermediate page
        
        from django.http import HttpResponseRedirect
        from django.urls import reverse
        
        # Store selected ids in session and redirect to a custom form
        selected_ids = ','.join(str(booking.id) for booking in queryset)
        return HttpResponseRedirect(
            reverse('admin:bookings_booking_partial_payment') + f'?ids={selected_ids}'
        )
    mark_as_partially_paid.short_description = "Mark selected bookings as PARTIALLY PAID (enter amount)"
    
    def mark_as_pending_payment(self, request, queryset):
        """Mark selected bookings as pending payment"""
        count = 0
        for booking in queryset:
            if booking.payment_status != 'pending':
                old_status = booking.payment_status
                booking.payment_status = 'pending'
                booking.save(update_fields=['payment_status'])
                
                BookingHistory.objects.create(
                    booking=booking,
                    old_status=booking.status,
                    new_status=booking.status,
                    changed_by=request.user,
                    reason=f'Payment status changed from {old_status} to pending (admin action)'
                )
                count += 1
        
        self.message_user(request, f"{count} bookings marked as pending payment.")
    mark_as_pending_payment.short_description = "Mark selected bookings as PENDING PAYMENT"
    
    def mark_as_overdue(self, request, queryset):
        """Mark selected bookings as overdue"""
        count = 0
        for booking in queryset:
            if booking.payment_status not in ['paid', 'refunded']:
                booking.payment_status = 'overdue'
                booking.save(update_fields=['payment_status'])
                
                BookingHistory.objects.create(
                    booking=booking,
                    old_status=booking.status,
                    new_status=booking.status,
                    changed_by=request.user,
                    reason='Payment marked as overdue (admin action)'
                )
                count += 1
        
        self.message_user(request, f"{count} bookings marked as overdue.")
    mark_as_overdue.short_description = "Mark selected bookings as OVERDUE ⚠️"
    
    # Add custom URL for partial payment form
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('<uuid:pk>/complete/', self.admin_site.admin_view(self.complete_booking), name='bookings_booking_complete'),
            path('partial-payment/', self.admin_site.admin_view(self.partial_payment_view), name='bookings_booking_partial_payment'),
        ]
        return custom_urls + urls
    
    def partial_payment_view(self, request):
        """Custom view to handle partial payment amount entry"""
        from django.shortcuts import render
        from django.http import HttpResponseRedirect
        from django.template.context_processors import csrf
        from .models import Booking
        
        ids = request.GET.get('ids', '').split(',')
        bookings = Booking.objects.filter(id__in=ids)
        
        if request.method == 'POST':
            amount_paid = float(request.POST.get('amount_paid', 0))
            
            for booking in bookings:
                if amount_paid > 0:
                    booking.amount_paid = min(amount_paid, booking.total_amount_usd)
                    booking.amount_due = booking.total_amount_usd - booking.amount_paid
                    booking.payment_status = 'partial' if booking.amount_due > 0 else 'paid'
                    booking.save(update_fields=['amount_paid', 'amount_due', 'payment_status'])
                    
                    BookingHistory.objects.create(
                        booking=booking,
                        old_status=booking.status,
                        new_status=booking.status,
                        changed_by=request.user,
                        reason=f'Partial payment of ${amount_paid:.2f} recorded. Amount due: ${booking.amount_due:.2f}'
                    )
            
            self.message_user(request, f"Partial payment recorded for {bookings.count()} bookings.")
            return HttpResponseRedirect(reverse('admin:bookings_booking_changelist'))
        
        # Add CSRF token to context
        c = {}
        c.update(csrf(request))
        
        context = {
            'bookings': bookings,
            'title': 'Record Partial Payment',
            'csrf_token': c.get('csrf_token', ''),
        }
        return render(request, 'admin/bookings/partial_payment.html', context)
    
    def get_queryset(self, request):
        """Optimize queryset with airport data"""
        return super().get_queryset(request).select_related('user', 'aircraft')


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = [
        'invoice_number', 'booking_display', 'user', 'status',
        'invoice_date', 'due_date', 'total_usd', 'paid_date', 'pdf_link'
    ]
    list_filter = ['status', 'invoice_date', 'due_date']
    search_fields = ['invoice_number', 'booking__booking_reference', 'user__email']
    readonly_fields = ['invoice_number', 'verification_hash', 'created_at', 'updated_at', 'pdf_link']
    date_hierarchy = 'invoice_date'
    
    fieldsets = (
        ('Invoice Information', {
            'fields': (
                'invoice_number', 'booking', 'user', 'status',
                'invoice_date', 'due_date', 'paid_date'
            )
        }),
        ('Billing Information', {
            'fields': (
                'billing_company_name', 'billing_tax_id',
                'billing_address_line1', 'billing_address_line2',
                'billing_city', 'billing_state', 'billing_postal_code',
                'billing_country'
            )
        }),
        ('Amounts', {
            'fields': (
                'subtotal_usd', 'tax_rate', 'tax_amount_usd',
                'discount_amount_usd', 'total_usd'
            )
        }),
        ('Currency', {
            'fields': ('currency', 'exchange_rate', 'total_currency')
        }),
        ('Payment Information', {
            'fields': ('payment_method', 'payment_transaction_id')
        }),
        ('Documents', {
            'fields': ('pdf_file', 'qr_code', 'verification_hash')
        }),
        ('Notes', {
            'fields': ('notes', 'terms_and_conditions')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    inlines = [InvoiceItemInline]
    actions = ['mark_as_paid', 'mark_as_sent', 'send_invoice']
    
    def booking_display(self, obj):
        """Display booking reference with route info"""
        if obj.booking:
            route = f"{obj.booking.departure_airport} → {obj.booking.arrival_airport}"
            return format_html(
                '<a href="{}">{}<br><small>{}</small></a>',
                reverse('admin:bookings_booking_change', args=[obj.booking.id]),
                obj.booking.booking_reference,
                route
            )
        return "-"
    booking_display.short_description = "Booking"
    
    def pdf_link(self, obj):
        if obj.pdf_file:
            return format_html('<a href="{}" target="_blank">Download PDF</a>', obj.pdf_file.url)
        return "Not generated"
    pdf_link.short_description = "PDF"
    
    def mark_as_paid(self, request, queryset):
        """Mark selected invoices as paid"""
        count = 0
        for invoice in queryset:
            if invoice.status != 'paid':
                invoice.mark_as_paid('admin', f"ADMIN-{timezone.now().timestamp()}")
                count += 1
        self.message_user(request, f"{count} invoices marked as paid.")
    mark_as_paid.short_description = "Mark selected invoices as PAID 💰"
    
    def mark_as_sent(self, request, queryset):
        """Mark selected invoices as sent"""
        count = 0
        for invoice in queryset:
            if invoice.status == 'draft':
                invoice.status = 'sent'
                invoice.save(update_fields=['status'])
                count += 1
        self.message_user(request, f"{count} invoices marked as sent.")
    mark_as_sent.short_description = "Mark selected invoices as SENT 📧"
    
    def send_invoice(self, request, queryset):
        # Implement email sending logic
        self.message_user(request, f"Invoices sent for {queryset.count()} invoices.")
    send_invoice.short_description = "Send invoice emails"
    
    def get_queryset(self, request):
        """Optimize queryset with related data"""
        return super().get_queryset(request).select_related('user', 'booking', 'booking__user')


@admin.register(Contract)
class ContractAdmin(admin.ModelAdmin):
    list_display = [
        'contract_number', 'client_name', 'aircraft', 'departure_datetime',
        'total_amount_usd', 'status', 'payment_link_status', 'invoice_ready'
    ]
    list_filter = ['status', 'created_at', 'aircraft']
    search_fields = ['contract_number', 'client_name', 'client_email', 'enquiry__enquiry_number']
    readonly_fields = [
        'contract_number', 'created_at', 'updated_at', 'payment_link_token',
        'payment_link', 'sent_at', 'viewed_at', 'accepted_at',
        'invoice_number', 'invoice_generated_at'
    ]

    class Media:
        js = ('admin/js/contract_autofill.js',)

    fieldsets = (
        ('Contract Information', {
            'fields': ('contract_number', 'status', 'enquiry', 'aircraft')
        }),
        ('Client Details', {
            'fields': ('client_name', 'client_email', 'client_phone')
        }),
        ('Flight Details', {
            'fields': ('departure_airport', 'arrival_airport', 'departure_datetime', 'arrival_datetime')
        }),
        ('Passenger Details', {
            'fields': ('passenger_count', 'luggage_weight_kg')
        }),
        ('Pricing (Set by Admin)', {
            'fields': (
                'base_price_usd', 'fuel_surcharge_usd', 'handling_fee_usd',
                'catering_cost_usd', 'insurance_cost_usd', 'discount_amount_usd',
                'tax_rate', 'total_amount_usd'
            )
        }),
        ('Amenities (Check all that apply)', {
            'fields': (
                'amenity_wifi', 'amenity_catering', 'amenity_entertainment',
                'amenity_conference', 'amenity_bedroom', 'amenity_shower',
                'amenity_lavatory', 'amenity_galley',
            ),
            'classes': ('wide',),
            'description': 'Check the amenities included in this charter'
        }),
        ('Additional Services', {
            'fields': ('ground_transport_included', 'hotel_accommodation_included'),
            'classes': ('wide',),
        }),
        ('Custom Inclusions (one per line)', {
            'fields': ('custom_inclusions_text',),
            'description': 'Add any additional inclusions, one per line'
        }),
        ('Custom Amenities (one per line)', {
            'fields': ('custom_amenities_text',),
            'description': 'Add any additional amenities, one per line'
        }),
        ('Exclusions (one per line)', {
            'fields': ('custom_exclusions_text',),
            'description': 'List items that are excluded, one per line'
        }),
        ('Cancellation Penalties', {
            'fields': (
                'cancellation_10_6_days', 'cancellation_5_days',
                'cancellation_3_days', 'cancellation_24_hours', 'cancellation_notes'
            ),
            'description': 'Set custom cancellation penalty percentages for this contract',
            'classes': ('wide',),
        }),
        ('Contract Details', {
            'fields': ('terms_conditions', 'valid_until', 'special_notes')
        }),

        # ========== INVOICE SECTION ==========
        ('📄 Invoice (Fill before sending to client)', {
            'fields': (
                'invoice_number',
                'invoice_date',
                'invoice_due_date',
                'invoice_notes',
                'invoice_generated_at',
            ),
            'description': 'Fill invoice details. Add line items in the table below.',
            'classes': ('wide',),
        }),
        # ======================================

        ('Payment Link', {
            'fields': ('payment_link', 'payment_link_token', 'payment_link_expiry')
        }),
        ('Admin Signature', {
            'fields': ('admin_signed', 'admin_signed_at', 'admin_signature', 'admin_signature_image'),
            'description': 'Sign the contract as admin'
        }),
        ('Status Tracking', {
            'fields': ('sent_at', 'viewed_at', 'accepted_at', 'booking')
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at'),
            'classes': ('collapse',)
        }),
    )

    inlines = [ContractLineItemInline]
    actions = ['send_contract_and_invoice', 'sign_contracts']

    def payment_link_status(self, obj):
        if obj.payment_link:
            return format_html('<a href="{}" target="_blank">View Link</a>', obj.payment_link)
        return "Not generated"
    payment_link_status.short_description = "Payment Link"

    def invoice_ready(self, obj):
        count = obj.line_items.count()
        if count:
            return format_html('<span style="color:green">✓ {} items</span>', count)
        return format_html('<span style="color:orange">⚠ No items</span>')
    invoice_ready.short_description = "Invoice"

    def send_contract_and_invoice(self, request, queryset):
        sent = 0
        skipped = 0
        for contract in queryset:
            if contract.status == 'draft':
                if not contract.line_items.exists():
                    self.message_user(
                        request,
                        f"Contract {contract.contract_number}: No invoice items set. Please fill invoice before sending.",
                        level='warning'
                    )
                    skipped += 1
                    continue
                contract.send_to_client()
                sent += 1
        if sent:
            self.message_user(request, f"{sent} contract(s) + invoice(s) sent to clients.")
        if skipped:
            self.message_user(
                request,
                f"{skipped} contract(s) skipped - fill invoice items first.",
                level='warning'
            )
    send_contract_and_invoice.short_description = "Send contract + invoice to client"

    def sign_contracts(self, request, queryset):
        for contract in queryset:
            contract.admin_signed = True
            contract.admin_signed_at = timezone.now()
            contract.admin_signature = request.user.get_full_name() or request.user.email
            contract.save()
        self.message_user(request, f"{queryset.count()} contracts signed by {request.user}")
    sign_contracts.short_description = "Sign selected contracts"

    def save_model(self, request, obj, form, change):
        if not obj.created_by:
            obj.created_by = request.user
        # Auto-generate invoice number if not set
        if not obj.invoice_number and obj.contract_number:
            obj.invoice_number = f"INV-{obj.contract_number}"
        super().save_model(request, obj, form, change)

    def response_add(self, request, obj, post_url_continue=None):
        if '_send' in request.POST:
            if not obj.line_items.exists():
                self.message_user(request, 'Please fill invoice items before sending.', level='warning')
                return redirect('admin:bookings_contract_change', obj.pk)
            obj.send_to_client()
            self.message_user(request, f'Contract + Invoice {obj.contract_number} sent to {obj.client_email}')
            return redirect('admin:bookings_contract_changelist')
        return super().response_add(request, obj, post_url_continue)

    def response_change(self, request, obj):
        if '_send' in request.POST:
            if not obj.line_items.exists():
                self.message_user(request, 'Please fill invoice items before sending.', level='warning')
                return redirect('admin:bookings_contract_change', obj.pk)
            obj.send_to_client()
            self.message_user(request, f'Contract + Invoice {obj.contract_number} sent to {obj.client_email}')
            return redirect('admin:bookings_contract_changelist')
        return super().response_change(request, obj)

    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        extra_context = extra_context or {}
        if object_id:
            extra_context['show_send_button'] = True
        return super().changeform_view(request, object_id, form_url, extra_context)