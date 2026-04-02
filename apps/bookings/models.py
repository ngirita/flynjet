import uuid
import hashlib
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from django.core.mail import send_mail
from django.template.loader import render_to_string
from decimal import Decimal
from django.conf import settings
from apps.core.models import TimeStampedModel, AuditModel
from django.core.files.base import ContentFile
from weasyprint import HTML
from io import BytesIO
import os
import logging

logger = logging.getLogger(__name__)

class Booking(TimeStampedModel):
    """Main booking model for flight charters"""
    
    BOOKING_STATUS = (
        ('draft', 'Draft'),
        ('pending', 'Pending Confirmation'),
        ('confirmed', 'Confirmed'),
        ('payment_pending', 'Payment Pending'),
        ('paid', 'Paid'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('refunded', 'Refunded'),
        ('no_show', 'No Show'),
        ('delayed', 'Delayed'),
    )
    
    FLIGHT_TYPES = (
        ('one_way', 'One Way'),
        ('round_trip', 'Round Trip'),
        ('multi_city', 'Multi City'),
        ('empty_leg', 'Empty Leg'),
    )
    
    PAYMENT_STATUS = (
        ('pending', 'Pending'),
        ('partial', 'Partially Paid'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
        ('partially_refunded', 'Partially Refunded'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    booking_reference = models.CharField(max_length=20, unique=True, db_index=True)
    
    # Relationships
    user = models.ForeignKey('accounts.User', on_delete=models.PROTECT, related_name='bookings')
    aircraft = models.ForeignKey('fleet.Aircraft', on_delete=models.SET_NULL, null=True, blank=True, related_name='bookings')
    
    # Booking Details
    flight_type = models.CharField(max_length=20, choices=FLIGHT_TYPES, default='one_way')
    status = models.CharField(max_length=20, choices=BOOKING_STATUS, default='draft', db_index=True)
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS, default='pending')
    
    # Flight Information
    departure_airport = models.CharField(max_length=3, help_text="IATA code")
    arrival_airport = models.CharField(max_length=3, help_text="IATA code")
    departure_datetime = models.DateTimeField(db_index=True)
    arrival_datetime = models.DateTimeField()
    return_departure_datetime = models.DateTimeField(null=True, blank=True)
    return_arrival_datetime = models.DateTimeField(null=True, blank=True)
    
    # Passenger/Cargo Details
    passenger_count = models.IntegerField(validators=[MinValueValidator(0)], default=0)
    crew_count = models.IntegerField(default=2)
    cargo_weight_kg = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    baggage_weight_kg = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Passenger Information (JSON for multiple passengers)
    passengers = models.JSONField(default=list, help_text="List of passenger details")
    
    # Flight Details
    flight_duration_hours = models.DecimalField(max_digits=5, decimal_places=2)
    flight_distance_nm = models.IntegerField()
    flight_distance_km = models.IntegerField()
    
    # Pricing
    base_price_usd = models.DecimalField(max_digits=12, decimal_places=2)
    fuel_surcharge_usd = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    handling_fee_usd = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    catering_cost_usd = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    overnight_charge_usd = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    cleaning_charge_usd = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    insurance_cost_usd = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount_amount_usd = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tax_amount_usd = models.DecimalField(max_digits=10, decimal_places=2)
    total_amount_usd = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Currency
    preferred_currency = models.CharField(max_length=3, default='USD')
    exchange_rate = models.DecimalField(max_digits=10, decimal_places=6, default=1)
    total_amount_preferred = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Payment Details
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    amount_due = models.DecimalField(max_digits=12, decimal_places=2)
    payment_due_date = models.DateTimeField()
    
    # Special Requests
    special_requests = models.TextField(blank=True)
    dietary_requirements = models.TextField(blank=True)
    medical_requirements = models.TextField(blank=True)
    
    # Catering
    catering_options = models.JSONField(default=list, blank=True)
    
    # Ground Transportation
    ground_transportation_required = models.BooleanField(default=False)
    ground_transportation_details = models.JSONField(default=dict, blank=True)
    
    # Hotel Requirements
    hotel_required = models.BooleanField(default=False)
    hotel_details = models.JSONField(default=dict, blank=True)
    
    # Insurance
    insurance_purchased = models.BooleanField(default=False)
    insurance_policy_number = models.CharField(max_length=100, blank=True)
    insurance_premium = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Cancellation Policy
    cancellation_policy = models.CharField(max_length=50, default='standard')
    cancellation_deadline = models.DateTimeField(null=True, blank=True)
    cancellation_fee_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.TextField(blank=True)
    cancelled_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='cancelled_bookings')
    
    # Refund
    refund_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    refund_status = models.CharField(max_length=20, blank=True)
    refund_processed_at = models.DateTimeField(null=True, blank=True)
    refund_transaction_id = models.CharField(max_length=200, blank=True)
    
    # Terms Acceptance
    terms_accepted = models.BooleanField(default=False)
    terms_accepted_at = models.DateTimeField(null=True, blank=True)
    terms_ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    # Confirmation
    confirmed_at = models.DateTimeField(null=True, blank=True)
    confirmed_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='confirmed_bookings')
    
    # Completion
    completed_at = models.DateTimeField(null=True, blank=True)
    actual_departure = models.DateTimeField(null=True, blank=True)
    actual_arrival = models.DateTimeField(null=True, blank=True)
    
    # Notes
    internal_notes = models.TextField(blank=True, help_text="Internal staff notes")
    customer_notes = models.TextField(blank=True, help_text="Notes visible to customer")
    
    # Metadata
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    source = models.CharField(max_length=50, default='website', choices=(
        ('website', 'Website'),
        ('mobile', 'Mobile App'),
        ('agent', 'Agent Portal'),
        ('api', 'API'),
        ('admin', 'Admin Panel'),
    ))
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['booking_reference']),
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['aircraft', 'departure_datetime']),
            models.Index(fields=['status', 'payment_status']),
            models.Index(fields=['departure_airport', 'arrival_airport']),
            models.Index(fields=['departure_datetime', 'status']),
        ]
    
    def __str__(self):
        return f"Booking {self.booking_reference} - {self.user.get_full_name()}"
    
    def save(self, *args, **kwargs):
        if not self.booking_reference:
            self.booking_reference = self.generate_booking_reference()
        super().save(*args, **kwargs)
    
    def generate_booking_reference(self):
        """Generate unique booking reference"""
        import random
        import string
        
        while True:
            reference = 'FJ' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
            if not Booking.objects.filter(booking_reference=reference).exists():
                return reference
    
    def calculate_totals(self):
        """Calculate total booking amount"""
        total = (self.base_price_usd + 
                self.fuel_surcharge_usd + 
                self.handling_fee_usd + 
                self.catering_cost_usd + 
                self.overnight_charge_usd + 
                self.cleaning_charge_usd + 
                self.insurance_cost_usd - 
                self.discount_amount_usd)
        
        # Add tax
        self.tax_amount_usd = total * Decimal('0.1')  # 10% tax
        total += self.tax_amount_usd
        
        self.total_amount_usd = total
        self.amount_due = total - self.amount_paid
        
        # Convert to preferred currency if needed
        if self.preferred_currency != 'USD':
            self.total_amount_preferred = total * self.exchange_rate
    
    def update_payment_status(self):
        """Update payment status based on amount paid"""
        if self.amount_paid >= self.total_amount_usd:
            self.payment_status = 'paid'
        elif self.amount_paid > 0:
            self.payment_status = 'partial'
        else:
            self.payment_status = 'pending'
        
        self.save(update_fields=['payment_status'])
    
    def confirm_booking(self, user):
        """Confirm the booking"""
        self.status = 'confirmed'
        self.confirmed_at = timezone.now()
        self.confirmed_by = user
        self.save(update_fields=['status', 'confirmed_at', 'confirmed_by'])
        
        # Update aircraft availability
        from apps.fleet.models import AircraftAvailability
        AircraftAvailability.objects.create(
            aircraft=self.aircraft,
            start_datetime=self.departure_datetime,
            end_datetime=self.arrival_datetime,
            is_available=False,
            booking=self,
            reason=f"Booked: {self.booking_reference}"
        )
        
        # Send confirmation email
        self.send_confirmation_email()
        
        logger.info(f"Booking {self.booking_reference} confirmed by {user.email}")
    
    def cancel_booking(self, user, reason=""):
        """Cancel the booking"""
        self.status = 'cancelled'
        self.cancelled_at = timezone.now()
        self.cancelled_by = user
        self.cancellation_reason = reason
        self.save(update_fields=['status', 'cancelled_at', 'cancelled_by', 'cancellation_reason'])
        
        # Remove aircraft availability
        from apps.fleet.models import AircraftAvailability
        AircraftAvailability.objects.filter(booking=self).delete()
        
        # Send cancellation email
        self.send_cancellation_email()
        
        logger.info(f"Booking {self.booking_reference} cancelled by {user.email}")
    
    def process_refund(self, amount, transaction_id, user):
        """Process refund for booking"""
        self.refund_amount = amount
        self.refund_status = 'processed'
        self.refund_processed_at = timezone.now()
        self.refund_transaction_id = transaction_id
        self.status = 'refunded'
        self.save(update_fields=['refund_amount', 'refund_status', 'refund_processed_at', 
                                'refund_transaction_id', 'status'])
        
        logger.info(f"Refund of ${amount} processed for booking {self.booking_reference}")
    
    def send_confirmation_email(self):
        """Send booking confirmation email"""
        subject = f"Booking Confirmation - {self.booking_reference}"
        
        context = {
            'booking': self,
            'user': self.user,
            'aircraft': self.aircraft,
        }
        
        html_message = render_to_string('emails/booking_confirmation.html', context)
        plain_message = render_to_string('emails/booking_confirmation.txt', context)
        
        send_mail(
            subject,
            plain_message,
            'info@flynjet.com',
            [self.user.email],
            html_message=html_message,
            fail_silently=False,
        )
    
    def send_cancellation_email(self):
        """Send booking cancellation email"""
        subject = f"Booking Cancellation - {self.booking_reference}"
        
        context = {
            'booking': self,
            'user': self.user,
            'aircraft': self.aircraft,
        }
        
        html_message = render_to_string('emails/booking_cancellation.html', context)
        plain_message = render_to_string('emails/booking_cancellation.txt', context)
        
        send_mail(
            subject,
            plain_message,
            'info@flynjet.com',
            [self.user.email],
            html_message=html_message,
            fail_silently=False,
        )


class BookingPassenger(models.Model):
    """Individual passenger details for a booking"""
    
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='passenger_details')
    
    # Personal Information
    title = models.CharField(max_length=10, choices=(
        ('mr', 'Mr.'),
        ('mrs', 'Mrs.'),
        ('ms', 'Ms.'),
        ('dr', 'Dr.'),
        ('prof', 'Prof.'),
    ))
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    date_of_birth = models.DateField()
    nationality = models.CharField(max_length=100)
    passport_number = models.CharField(max_length=50)
    passport_expiry = models.DateField()
    passport_country = models.CharField(max_length=100)
    
    # Contact
    email = models.EmailField(blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
    
    # Special Requirements
    dietary_requirements = models.TextField(blank=True)
    medical_requirements = models.TextField(blank=True)
    special_assistance = models.BooleanField(default=False)
    
    # Seat
    seat_number = models.CharField(max_length=10, blank=True)
    
    # Baggage
    baggage_count = models.IntegerField(default=1)
    baggage_weight_kg = models.DecimalField(max_digits=5, decimal_places=2, default=23)
    
    # Emergency Contact
    emergency_contact_name = models.CharField(max_length=200)
    emergency_contact_phone = models.CharField(max_length=20)
    emergency_contact_relation = models.CharField(max_length=100)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['booking', 'passport_number']
    
    def __str__(self):
        return f"{self.title} {self.first_name} {self.last_name} - {self.booking.booking_reference}"
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"


class BookingAddon(models.Model):
    """Additional services for bookings"""
    
    ADDON_TYPES = (
        ('catering', 'Catering'),
        ('transport', 'Ground Transport'),
        ('hotel', 'Hotel'),
        ('insurance', 'Insurance'),
        ('entertainment', 'Entertainment'),
        ('crew', 'Additional Crew'),
        ('fuel', 'Extra Fuel'),
        ('cleaning', 'Extra Cleaning'),
    )
    
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='addons')
    addon_type = models.CharField(max_length=20, choices=ADDON_TYPES)
    name = models.CharField(max_length=200)
    description = models.TextField()
    quantity = models.IntegerField(default=1)
    unit_price_usd = models.DecimalField(max_digits=10, decimal_places=2)
    total_price_usd = models.DecimalField(max_digits=10, decimal_places=2)
    is_required = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def save(self, *args, **kwargs):
        self.total_price_usd = self.unit_price_usd * self.quantity
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.name} - {self.booking.booking_reference}"


class BookingHistory(models.Model):
    """Track all booking status changes"""
    
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='history')
    old_status = models.CharField(max_length=20)
    new_status = models.CharField(max_length=20)
    changed_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True)
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = "Booking histories"
    
    def __str__(self):
        return f"{self.booking.booking_reference}: {self.old_status} -> {self.new_status}"


class Invoice(TimeStampedModel):
    """Invoice model for bookings"""
    
    INVOICE_STATUS = (
        ('draft', 'Draft'),
        ('sent', 'Sent'),
        ('paid', 'Paid'),
        ('overdue', 'Overdue'),
        ('cancelled', 'Cancelled'),
        ('refunded', 'Refunded'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice_number = models.CharField(max_length=50, unique=True, db_index=True)
    booking = models.ForeignKey(Booking, on_delete=models.PROTECT, related_name='invoices')
    user = models.ForeignKey('accounts.User', on_delete=models.PROTECT, related_name='invoices')
    
    # Invoice Details
    status = models.CharField(max_length=20, choices=INVOICE_STATUS, default='draft')
    invoice_date = models.DateField(default=timezone.now)
    due_date = models.DateField()
    paid_date = models.DateTimeField(null=True, blank=True)
    
    # Billing Information
    billing_company_name = models.CharField(max_length=200, blank=True)
    billing_tax_id = models.CharField(max_length=100, blank=True)
    billing_address_line1 = models.CharField(max_length=255)
    billing_address_line2 = models.CharField(max_length=255, blank=True)
    billing_city = models.CharField(max_length=100)
    billing_state = models.CharField(max_length=100)
    billing_postal_code = models.CharField(max_length=20)
    billing_country = models.CharField(max_length=100)
    
    # Amounts
    subtotal_usd = models.DecimalField(max_digits=12, decimal_places=2)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=10)
    tax_amount_usd = models.DecimalField(max_digits=12, decimal_places=2)
    discount_amount_usd = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_usd = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Currency
    currency = models.CharField(max_length=3, default='USD')
    exchange_rate = models.DecimalField(max_digits=10, decimal_places=6, default=1)
    total_currency = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Payment Information
    payment_method = models.CharField(max_length=50, blank=True)
    payment_transaction_id = models.CharField(max_length=200, blank=True)
    
    # PDF
    pdf_file = models.FileField(upload_to='invoices/', blank=True)
    
    # Notes
    notes = models.TextField(blank=True)
    terms_and_conditions = models.TextField(blank=True)
    
    # QR Code (for verification)
    qr_code = models.ImageField(upload_to='invoices/qrcodes/', blank=True)
    verification_hash = models.CharField(max_length=64, unique=True)
    
    class Meta:
        ordering = ['-invoice_date']
        indexes = [
            models.Index(fields=['invoice_number']),
            models.Index(fields=['booking', 'status']),
            models.Index(fields=['user', '-invoice_date']),
        ]
    
    def __str__(self):
        return f"Invoice {self.invoice_number} - {self.booking.booking_reference}"
    
    def save(self, *args, **kwargs):
        if not self.invoice_number:
            self.invoice_number = self.generate_invoice_number()
        if not self.verification_hash:
            self.generate_verification_hash()
        super().save(*args, **kwargs)
    
    # INSIDE Invoice class — replace the broken generate_invoice_number
    def generate_invoice_number(self):
        """Generate unique invoice number"""
        year = timezone.now().year
        month = timezone.now().month
        last_invoice = Invoice.objects.filter(
            invoice_number__startswith=f'INV-{year}{month:02d}'
        ).order_by('-invoice_number').first()

        if last_invoice:
            last_number = int(last_invoice.invoice_number.split('-')[-1])
            new_number = last_number + 1
        else:
            new_number = 1

        return f"INV-{year}{month:02d}-{new_number:04d}"
            
    def generate_verification_hash(self):
        """Generate verification hash for QR code"""
        data = f"{self.invoice_number}{self.total_usd}{self.booking.booking_reference}"
        self.verification_hash = hashlib.sha256(data.encode()).hexdigest()
    
    def mark_as_paid(self, payment_method, transaction_id):
        """Mark invoice as paid"""
        self.status = 'paid'
        self.paid_date = timezone.now()
        self.payment_method = payment_method
        self.payment_transaction_id = transaction_id
        self.save(update_fields=['status', 'paid_date', 'payment_method', 'payment_transaction_id'])
        
        # Update booking payment status
        self.booking.update_payment_status()
        
        logger.info(f"Invoice {self.invoice_number} marked as paid")


class InvoiceItem(models.Model):
    """Line items for invoice"""
    
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='items')
    description = models.CharField(max_length=255)
    quantity = models.IntegerField(default=1)
    unit_price_usd = models.DecimalField(max_digits=10, decimal_places=2)
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=10)
    line_total_usd = models.DecimalField(max_digits=12, decimal_places=2)
    
    def save(self, *args, **kwargs):
        # Convert to Decimal to avoid float multiplication issues
        from decimal import Decimal
        
        quantity = Decimal(str(self.quantity))
        unit_price = self.unit_price_usd
        discount = Decimal(str(self.discount_percentage)) / Decimal('100')
        tax = Decimal(str(self.tax_rate)) / Decimal('100')
        
        # Calculate line total
        subtotal = quantity * unit_price
        discount_amount = subtotal * discount
        after_discount = subtotal - discount_amount
        tax_amount = after_discount * tax
        self.line_total_usd = after_discount + tax_amount
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.description} - {self.invoice.invoice_number}"
    
# Add to apps/bookings/models.py

class Contract(models.Model):
    """Contract created by admin from enquiry"""
    
    CONTRACT_STATUS = (
        ('draft', 'Draft'),
        ('sent', 'Sent to Client'),
        ('viewed', 'Viewed by Client'),
        ('accepted', 'Accepted'),
        ('payment_initiated', 'Payment Initiated'),
        ('paid', 'Paid'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    contract_number = models.CharField(max_length=20, unique=True, db_index=True)
    enquiry = models.ForeignKey('fleet.Enquiry', on_delete=models.PROTECT, related_name='contracts')
    
    # Client Details (pre-filled from enquiry)
    client_name = models.CharField(max_length=200)
    client_email = models.EmailField()
    client_phone = models.CharField(max_length=20)
    
    # Flight Details
    aircraft = models.ForeignKey('fleet.Aircraft', on_delete=models.SET_NULL, null=True, blank=True, related_name='contracts')
    departure_airport = models.CharField(max_length=3)
    arrival_airport = models.CharField(max_length=3)
    departure_datetime = models.DateTimeField()
    arrival_datetime = models.DateTimeField()
    
    # Passenger Details
    passenger_count = models.IntegerField()
    luggage_weight_kg = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Pricing (Set by admin)
    base_price_usd = models.DecimalField(max_digits=12, decimal_places=2)
    fuel_surcharge_usd = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    handling_fee_usd = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    catering_cost_usd = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    insurance_cost_usd = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount_amount_usd = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=10)
    total_amount_usd = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Contract Details
    terms_conditions = models.TextField(default="Standard terms and conditions apply...")
    valid_until = models.DateTimeField()
    special_notes = models.TextField(blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=CONTRACT_STATUS, default='draft')
    sent_at = models.DateTimeField(null=True, blank=True)
    viewed_at = models.DateTimeField(null=True, blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    
    # Payment Link
    payment_link = models.URLField(blank=True)
    payment_link_token = models.CharField(max_length=64, unique=True, blank=True)
    payment_link_expiry = models.DateTimeField(null=True, blank=True)
    
    # Conversion to Booking
    booking = models.ForeignKey('bookings.Booking', on_delete=models.SET_NULL, null=True, blank=True, related_name='contract')
    
    # ========== NEW FIELDS - Inclusions & Exclusions ==========
    # Dynamic Inclusions & Exclusions
    inclusions = models.JSONField(default=list, blank=True, help_text='List of included items. Format: [{"item": "Item name", "status": "included", "notes": "notes"}]')
    exclusions = models.JSONField(default=list, blank=True, help_text='List of excluded items. Format: [{"item": "Item name", "status": "excluded", "notes": "notes"}]')
    amenities = models.JSONField(default=list, blank=True, help_text='List of amenities. Format: [{"name": "Amenity", "details": "Details"}]')
    
    # ========== EASY CHECKBOX AMENITIES ==========
    amenity_wifi = models.BooleanField(default=True, verbose_name="✓ WiFi")
    amenity_catering = models.BooleanField(default=True, verbose_name="✓ Catering")
    amenity_entertainment = models.BooleanField(default=True, verbose_name="✓ Entertainment System")
    amenity_conference = models.BooleanField(default=False, verbose_name="✓ Conference Table")
    amenity_bedroom = models.BooleanField(default=False, verbose_name="✓ Bedroom")
    amenity_shower = models.BooleanField(default=False, verbose_name="✓ Shower")
    amenity_lavatory = models.BooleanField(default=True, verbose_name="✓ Lavatory")
    amenity_galley = models.BooleanField(default=True, verbose_name="✓ Full Galley")
    
    # ========== EASY CHECKBOX SERVICES ==========
    ground_transport_included = models.BooleanField(default=False, verbose_name="✓ Ground Transportation")
    hotel_accommodation_included = models.BooleanField(default=False, verbose_name="✓ Hotel Accommodation")
    
    # ========== CUSTOM TEXT FIELDS (Simple!) ==========
    custom_inclusions_text = models.TextField(blank=True, help_text="Additional inclusions (one per line)")
    custom_amenities_text = models.TextField(blank=True, help_text="Additional amenities (one per line)")
    custom_exclusions_text = models.TextField(blank=True, help_text="Exclusions (one per line)")
    
    # ========== CANCELLATION PENALTIES (Admin Customizable) ==========
    cancellation_10_6_days = models.DecimalField(max_digits=5, decimal_places=2, default=30, 
                                                  help_text="% charge for 10-6 days before departure", verbose_name="10-6 days penalty %")
    cancellation_5_days = models.DecimalField(max_digits=5, decimal_places=2, default=40, 
                                               help_text="% charge for 5 days before departure", verbose_name="5 days penalty %")
    cancellation_3_days = models.DecimalField(max_digits=5, decimal_places=2, default=50, 
                                               help_text="% charge for 3 days before departure", verbose_name="3 days penalty %")
    cancellation_24_hours = models.DecimalField(max_digits=5, decimal_places=2, default=60, 
                                                 help_text="% charge for 24 hours before departure", verbose_name="24 hours penalty %")
    cancellation_notes = models.TextField(blank=True, help_text="Additional cancellation terms", verbose_name="Cancellation Notes")
    
    # Add these fields to the existing Contract model in apps/bookings/models.py
    # Add AFTER the existing cancellation_notes field:

    # ========== INVOICE FIELDS (Admin fills separately) ==========
    invoice_number = models.CharField(max_length=50, blank=True)
    invoice_date = models.DateField(null=True, blank=True)
    invoice_due_date = models.DateField(null=True, blank=True)
    invoice_notes = models.TextField(blank=True, help_text="Additional invoice notes")

    # Invoice line items as JSON for flexibility
    # Format: [{"description": "Base Charter Fee", "amount": 5000.00}, ...]
    invoice_line_items = models.JSONField(
        default=list, blank=True,
        help_text='Invoice line items. Format: [{"description": "Item", "amount": 1000.00}]'
    )

    # Invoice PDF (generated separately from contract)
    invoice_pdf_file = models.FileField(upload_to='invoices/contract/', blank=True, null=True)
    invoice_generated_at = models.DateTimeField(null=True, blank=True)

    # Admin Signature
    admin_signed = models.BooleanField(default=False)
    admin_signed_at = models.DateTimeField(null=True, blank=True)
    admin_signature = models.TextField(blank=True, help_text="Admin signature text or name")
    admin_signature_image = models.ImageField(upload_to='signatures/', blank=True, null=True)
    
    # ========== PDF AND SEND TRACKING FIELDS ==========
    pdf_file = models.FileField(upload_to='contracts/', blank=True, null=True)
    send_count = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, related_name='created_contracts')
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Contract {self.contract_number} - {self.client_name}"
    
    def save(self, *args, **kwargs):
        if not self.contract_number:
            self.contract_number = self.generate_contract_number()
        if not self.total_amount_usd:
            self.calculate_total()
        super().save(*args, **kwargs)
    
    def generate_contract_number(self):
        import random
        import string
        timestamp = timezone.now().strftime('%Y%m')
        random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        return f"CTR{timestamp}{random_str}"
    
    def calculate_total(self):
        subtotal = (self.base_price_usd + self.fuel_surcharge_usd + 
                   self.handling_fee_usd + self.catering_cost_usd + 
                   self.insurance_cost_usd - self.discount_amount_usd)
        tax = subtotal * (self.tax_rate / 100)
        self.total_amount_usd = subtotal + tax
    
    def generate_payment_link(self):
        """Generate unique payment link for this contract"""
        import secrets
        token = secrets.token_urlsafe(32)
        self.payment_link_token = token
        self.payment_link_expiry = timezone.now() + timezone.timedelta(days=7)
        self.payment_link = f"{settings.SITE_URL}/payments/contract/{token}/"
        # Save all three fields
        self.save(update_fields=['payment_link_token', 'payment_link_expiry', 'payment_link'])
        print(f"Generated payment link: {self.payment_link}")  # Debug
        return self.payment_link
    
    def generate_pdf(self):
        """Generate PDF contract with payment link"""
        from django.conf import settings
        from django.template.loader import render_to_string
        from weasyprint import HTML
        from io import BytesIO
        import os
        
        # Get logo path as file:// URL for WeasyPrint
        logo_url = None
        logo_path = os.path.join(settings.BASE_DIR, 'static', 'images', 'logo.png')
        if os.path.exists(logo_path):
            # Convert Windows path to URL format (C:/Users/...)
            logo_url = f'file:///{logo_path.replace(os.sep, "/")}'
            print(f"Logo found at: {logo_url}")  # Debug
        
        # Render HTML template
        html_string = render_to_string('admin/contracts/contract_pdf.html', {
            'contract': self,
            'company_logo': logo_url,
            'created_at': self.created_at,
        })
        
        # Generate PDF
        pdf_file = BytesIO()
        HTML(string=html_string).write_pdf(pdf_file)
        pdf_file.seek(0)
        
        # Save PDF file
        filename = f"contract_{self.contract_number}.pdf"
        self.pdf_file.save(filename, ContentFile(pdf_file.getvalue()))
        self.save(update_fields=['pdf_file'])
        
        return self.pdf_file

    def generate_invoice_number_for_contract(self):
        """Auto-generate invoice number tied to this contract"""
        if not self.invoice_number:
            self.invoice_number = f"INV-{self.contract_number}"
        return self.invoice_number

    def generate_invoice_pdf(self):
        """Generate the invoice PDF (separate from contract PDF)"""
        import os
        from django.conf import settings
        from django.template.loader import render_to_string
        from weasyprint import HTML
        from io import BytesIO
        from apps.core.models import CryptoWallet, BankDetail, CompanyContact

        logo_url = None
        logo_path = os.path.join(settings.BASE_DIR, 'static', 'images', 'logo.png')
        if os.path.exists(logo_path):
            logo_url = f'file:///{logo_path.replace(os.sep, "/")}'

        crypto_wallets = CryptoWallet.objects.filter(is_active=True).order_by('sort_order')
        bank_details = BankDetail.objects.filter(is_active=True).order_by('sort_order')
        company_contacts = CompanyContact.objects.filter(is_active=True).order_by('sort_order')

        html_string = render_to_string('admin/contracts/invoice_pdf.html', {
            'contract': self,
            'company_logo': logo_url,
            'crypto_wallets': crypto_wallets,
            'bank_details': bank_details,
            'company_contacts': company_contacts,
        })

        pdf_file = BytesIO()
        HTML(string=html_string).write_pdf(pdf_file)
        pdf_file.seek(0)

        filename = f"invoice_{self.contract_number}.pdf"
        self.invoice_pdf_file.save(filename, ContentFile(pdf_file.getvalue()))
        self.invoice_generated_at = timezone.now()
        self.save(update_fields=['invoice_pdf_file', 'invoice_generated_at'])

        return self.invoice_pdf_file
    
    def send_to_client(self):
        """Send CONTRACT + INVOICE to client. Payment link lives on the invoice."""
        from django.core.mail import EmailMultiAlternatives
        from django.template.loader import render_to_string
        from django.conf import settings

        # 1. Generate payment link if not already done
        if not self.payment_link_token:
            self.generate_payment_link()

        # 2. Ensure invoice number exists
        if not self.invoice_number:
            self.generate_invoice_number_for_contract()
            self.save(update_fields=['invoice_number'])

        # 3. Generate contract PDF
        if not self.pdf_file or self.send_count == 0:
            self.generate_pdf()

        # 4. Always regenerate invoice PDF so payment link is current
        self.generate_invoice_pdf()

        # 5. Build and send email
        subject = f"Charter Contract & Invoice - {self.contract_number}"

        context = {
            'contract': self,
            'payment_link': self.payment_link,
            'site_url': settings.SITE_URL,
        }

        html_message = render_to_string('emails/contract_to_client.html', context)
        plain_message = f"""Dear {self.client_name},

    Please find attached:
    1. Your charter CONTRACT ({self.contract_number})
    2. Your INVOICE ({self.invoice_number}) — contains your secure payment link

    Summary:
    Aircraft : {self.aircraft.manufacturer.name} {self.aircraft.model}
    Route    : {self.departure_airport} → {self.arrival_airport}
    Date     : {self.departure_datetime.strftime('%B %d, %Y')}
    Total    : ${self.total_amount_usd:,.2f}

    Payment link (also in the invoice PDF):
    {self.payment_link}

    Valid until {self.valid_until.strftime('%B %d, %Y')}.

    Regards,
    FlynJet Team
    """

        email = EmailMultiAlternatives(
            subject=subject,
            body=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[self.client_email],
        )
        email.attach_alternative(html_message, "text/html")

        # Attach contract PDF
        if self.pdf_file:
            self.pdf_file.seek(0)
            email.attach(
                filename=f"Contract_{self.contract_number}.pdf",
                content=self.pdf_file.read(),
                mimetype='application/pdf'
            )

        # Attach invoice PDF
        if self.invoice_pdf_file:
            self.invoice_pdf_file.seek(0)
            email.attach(
                filename=f"Invoice_{self.invoice_number}.pdf",
                content=self.invoice_pdf_file.read(),
                mimetype='application/pdf'
            )

        email.send(fail_silently=False)

        # Update tracking
        self.send_count += 1
        self.status = 'sent'
        self.sent_at = timezone.now()
        self.save(update_fields=['send_count', 'status', 'sent_at'])

        logger.info(
            f"Contract {self.contract_number} + Invoice {self.invoice_number} "
            f"sent to {self.client_email} (send #{self.send_count})"
        )
        
    def get_default_inclusions(self):
        """Return default inclusions if none set"""
        if self.inclusions:
            return self.inclusions
        return [
            {"item": "Aircraft, Crew, Maintenance, Insurance & Fuel", "status": "included", "notes": "Included"},
            {"item": "Navigation (En-route, Approach, Aerodrome)", "status": "included", "notes": "Included"},
            {"item": "Meteorological Charges", "status": "included", "notes": "Included"},
            {"item": "Airport (Landing, Parking) Fees", "status": "included", "notes": "Included"},
            {"item": "Approach & Landing Fees", "status": "included", "notes": "Included"},
            {"item": "Over-Flight + Landing Clearances", "status": "included", "notes": "Included"},
            {"item": "In-flight Catering & Refreshments", "status": "included", "notes": "As requested"},
            {"item": "Handling", "status": "included", "notes": "Included"},
            {"item": "Crew Accommodation", "status": "included", "notes": "4-star minimum"},
            {"item": "Crew Transport to/from Hotel", "status": "included", "notes": "Included"},
        ]

    def get_default_amenities(self):
        """Return default amenities if none set"""
        if self.amenities:
            return self.amenities
        return [
            {"name": "WiFi", "details": "High-speed satellite internet"},
            {"name": "Entertainment System", "details": "4K screens, streaming"},
            {"name": "Conference Table", "details": "Seats 6 with power outlets"},
            {"name": "Full Galley", "details": "Gourmet meal preparation"},
            {"name": "Lavatory", "details": "Full-size with amenities"},
        ]
    
    def get_inclusions_list(self):
        """Convert checkboxes and text to inclusion list for PDF"""
        inclusions = [
            {"item": "Aircraft, Crew, Maintenance, Insurance & Fuel", "status": "included", "notes": "Included"},
            {"item": "Navigation (En-route, Approach, Aerodrome)", "status": "included", "notes": "Included"},
            {"item": "Meteorological Charges", "status": "included", "notes": "Included"},
            {"item": "Airport (Landing, Parking) Fees", "status": "included", "notes": "Included"},
            {"item": "Approach & Landing Fees", "status": "included", "notes": "Included"},
            {"item": "Over-Flight + Landing Clearances", "status": "included", "notes": "Included"},
            {"item": "In-flight Catering & Refreshments", "status": "included", "notes": "As requested"},
            {"item": "Handling", "status": "included", "notes": "Included"},
            {"item": "Crew Accommodation", "status": "included", "notes": "4-star minimum"},
            {"item": "Crew Transport to/from Hotel", "status": "included", "notes": "Included"},
        ]
        
        # Add ground transport if checked
        if self.ground_transport_included:
            inclusions.append({"item": "Ground Transportation", "status": "included", "notes": "Airport transfers"})
        
        # Add hotel if checked
        if self.hotel_accommodation_included:
            inclusions.append({"item": "Hotel Accommodation", "status": "included", "notes": "As arranged"})
        
        # Add custom inclusions from text field (one per line)
        if self.custom_inclusions_text:
            for line in self.custom_inclusions_text.strip().split('\n'):
                if line.strip():
                    inclusions.append({
                        "item": line.strip(),
                        "status": "included",
                        "notes": "As requested"
                    })
        
        return inclusions

    def get_amenities_list(self):
        """Convert checkboxes and text to amenities list for PDF"""
        amenities = []
        
        # Add amenities from checkboxes
        if self.amenity_wifi:
            amenities.append({"name": "WiFi", "details": "High-speed internet"})
        if self.amenity_catering:
            amenities.append({"name": "Catering", "details": "Gourmet meals & beverages"})
        if self.amenity_entertainment:
            amenities.append({"name": "Entertainment System", "details": "Movies, music, streaming"})
        if self.amenity_conference:
            amenities.append({"name": "Conference Table", "details": "Seats 6 with power outlets"})
        if self.amenity_bedroom:
            amenities.append({"name": "Bedroom", "details": "Private suite"})
        if self.amenity_shower:
            amenities.append({"name": "Shower", "details": "Full shower facility"})
        if self.amenity_lavatory:
            amenities.append({"name": "Lavatory", "details": "Private restroom"})
        if self.amenity_galley:
            amenities.append({"name": "Full Galley", "details": "Gourmet meal preparation"})
        
        # Add custom amenities from text field (one per line)
        if self.custom_amenities_text:
            for line in self.custom_amenities_text.strip().split('\n'):
                if line.strip():
                    amenities.append({"name": line.strip(), "details": "Available"})
        
        return amenities

    def get_exclusions_list(self):
        """Get exclusions for PDF"""
        exclusions = []
        
        # Add exclusions from text field (one per line)
        if self.custom_exclusions_text:
            for line in self.custom_exclusions_text.strip().split('\n'):
                if line.strip():
                    exclusions.append({
                        "item": line.strip(),
                        "status": "excluded",
                        "notes": "Available at extra cost"
                    })
        
        return exclusions

class ContractLineItem(models.Model):
    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, related_name='line_items')
    description = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=8, decimal_places=2, default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)

    @property
    def amount(self):
        return self.quantity * self.unit_price

    def __str__(self):
        return f"{self.description} — ${self.amount:,.2f}"