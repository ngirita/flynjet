import uuid
import hashlib
import hmac
from decimal import Decimal
from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone
from apps.core.models import TimeStampedModel
import logging

logger = logging.getLogger(__name__)

class Payment(TimeStampedModel):
    """Main payment model for all transactions"""
    
    PAYMENT_METHODS = (
        ('card', 'Card (Visa/Mastercard via Paystack)'),
        ('crypto', 'Cryptocurrency (BTC / USDT)'),  
        ('usdt_erc20', 'USDT (ERC-20)'),
        ('usdt_trc20', 'USDT (TRC-20)'),
        ('bitcoin', 'Bitcoin'),
        ('ethereum', 'Ethereum'),
        ('bank_transfer', 'Bank Transfer'),
        ('wire_transfer', 'Wire Transfer'),
    )
    
    PAYMENT_STATUS = (
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
        ('partially_refunded', 'Partially Refunded'),
        ('cancelled', 'Cancelled'),
        ('disputed', 'Disputed'),
    )
    
    PAYMENT_TYPES = (
        ('booking', 'Booking Payment'),
        ('deposit', 'Deposit'),
        ('installment', 'Installment'),
        ('refund', 'Refund'),
        ('membership', 'Membership Fee'),
        ('subscription', 'Subscription'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transaction_id = models.CharField(max_length=200, unique=True, db_index=True)
    
    # Relationships
    user = models.ForeignKey('accounts.User', on_delete=models.PROTECT, related_name='payments')
    booking = models.ForeignKey('bookings.Booking', on_delete=models.PROTECT, related_name='payments', null=True, blank=True)
    invoice = models.ForeignKey('bookings.Invoice', on_delete=models.PROTECT, related_name='payments', null=True, blank=True)
    
    # Payment Details
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS)
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPES, default='booking')
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS, default='pending', db_index=True)
    
    # Amounts
    amount_usd = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    currency = models.CharField(max_length=3, default='USD')
    exchange_rate = models.DecimalField(max_digits=10, decimal_places=6, default=1)
    amount_currency = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Fee Breakdown
    processing_fee_usd = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    gateway_fee_usd = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    net_amount_usd = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Payment Provider Details
    provider = models.CharField(max_length=50)  # paystack, crypto, manual
    provider_payment_id = models.CharField(max_length=200, blank=True)
    provider_charge_id = models.CharField(max_length=200, blank=True)
    provider_customer_id = models.CharField(max_length=200, blank=True)
    
    # Card Details (tokenized/encrypted)
    card_last4 = models.CharField(max_length=4, blank=True)
    card_brand = models.CharField(max_length=50, blank=True)
    card_expiry_month = models.CharField(max_length=2, blank=True)
    card_expiry_year = models.CharField(max_length=4, blank=True)
    card_token = models.CharField(max_length=200, blank=True)
    
    # Crypto Details
    crypto_wallet_address = models.CharField(max_length=200, blank=True)
    crypto_transaction_hash = models.CharField(max_length=200, blank=True)
    crypto_network = models.CharField(max_length=50, blank=True)
    crypto_confirmations = models.IntegerField(default=0)
    crypto_required_confirmations = models.IntegerField(default=12)
    
    # Bank Transfer Details
    bank_name = models.CharField(max_length=200, blank=True)
    bank_account_last4 = models.CharField(max_length=4, blank=True)
    bank_routing_number = models.CharField(max_length=50, blank=True)
    bank_reference = models.CharField(max_length=200, blank=True)
    
    # Status Tracking
    payment_date = models.DateTimeField(null=True, blank=True)
    failure_reason = models.TextField(blank=True)
    failure_code = models.CharField(max_length=100, blank=True)
    
    # Refund Details
    refund_amount_usd = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    refund_reason = models.TextField(blank=True)
    refund_date = models.DateTimeField(null=True, blank=True)
    refund_transaction_id = models.CharField(max_length=200, blank=True)
    refunded_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='payment_refunds')
    
    # Metadata
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    receipt_url = models.URLField(blank=True)
    receipt_sent = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['transaction_id']),
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['booking', 'status']),
            models.Index(fields=['provider', 'provider_payment_id']),
            models.Index(fields=['status', 'payment_date']),
            models.Index(fields=['crypto_transaction_hash']),
        ]
    
    def __str__(self):
        return f"Payment {self.transaction_id} - {self.amount_usd} {self.currency}"
    
    def save(self, *args, **kwargs):
        if not self.transaction_id:
            self.transaction_id = self.generate_transaction_id()
        if not self.net_amount_usd:
            self.net_amount_usd = self.amount_usd - self.processing_fee_usd - self.gateway_fee_usd
        super().save(*args, **kwargs)
    
    def generate_transaction_id(self):
        """Generate unique transaction ID"""
        import random
        import string
        timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
        random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        return f"TXN{timestamp}{random_str}"
    
    def mark_as_completed(self):
        """
        Mark payment as completed.
        All booking/invoice/document updates are handled by the signal.
        This method only updates the payment status.
        """
        self.status = 'completed'
        self.payment_date = timezone.now()
        self.save(update_fields=['status', 'payment_date'])
        logger.info(f"Payment {self.transaction_id} marked as completed")
        
    def mark_as_failed(self, reason, code=''):
        """Mark payment as failed"""
        self.status = 'failed'
        self.failure_reason = reason
        self.failure_code = code
        self.save(update_fields=['status', 'failure_reason', 'failure_code'])
        logger.warning(f"Payment {self.transaction_id} failed: {reason}")
    
    def process_refund(self, amount, reason, user):
        """Process refund for this payment"""
        self.refund_amount_usd = amount
        self.refund_reason = reason
        self.refund_date = timezone.now()
        self.refund_transaction_id = f"REF{self.transaction_id}"
        self.refunded_by = user
        
        if amount >= self.amount_usd:
            self.status = 'refunded'
        else:
            self.status = 'partially_refunded'
        
        self.save(update_fields=['refund_amount_usd', 'refund_reason', 'refund_date', 
                                'refund_transaction_id', 'refunded_by', 'status'])
        
        if self.booking:
            self.booking.process_refund(amount, self.refund_transaction_id, user)
        
        logger.info(f"Refund of ${amount} processed for payment {self.transaction_id}")
    
    def send_receipt(self):
        """Send payment receipt email"""
        from django.core.mail import send_mail
        from django.template.loader import render_to_string
        
        subject = f"Payment Receipt - {self.transaction_id}"
        
        context = {
            'payment': self,
            'user': self.user,
            'booking': self.booking,
        }
        
        html_message = render_to_string('emails/payment_receipt.html', context)
        plain_message = render_to_string('emails/payment_receipt.txt', context)
        
        send_mail(
            subject,
            plain_message,
            'info@flynjet.com',
            [self.user.email],
            html_message=html_message,
            fail_silently=False,
        )
        
        self.receipt_sent = True
        self.save(update_fields=['receipt_sent'])


class PaymentMethod(models.Model):
    """Saved payment methods for users"""
    
    user = models.ForeignKey('accounts.User', on_delete=models.CASCADE, related_name='payment_methods')
    payment_type = models.CharField(max_length=20, choices=Payment.PAYMENT_METHODS)
    
    card_last4 = models.CharField(max_length=4, blank=True)
    card_brand = models.CharField(max_length=50, blank=True)
    card_expiry_month = models.CharField(max_length=2, blank=True)
    card_expiry_year = models.CharField(max_length=4, blank=True)
    card_holder_name = models.CharField(max_length=200, blank=True)
    card_token = models.CharField(max_length=200)
    
    bank_name = models.CharField(max_length=200, blank=True)
    bank_account_last4 = models.CharField(max_length=4, blank=True)
    bank_routing_number = models.CharField(max_length=50, blank=True)
    bank_account_type = models.CharField(max_length=50, blank=True)
    
    crypto_wallet_address = models.CharField(max_length=200, blank=True)
    crypto_network = models.CharField(max_length=50, blank=True)
    
    billing_address_line1 = models.CharField(max_length=255, blank=True)
    billing_address_line2 = models.CharField(max_length=255, blank=True)
    billing_city = models.CharField(max_length=100, blank=True)
    billing_state = models.CharField(max_length=100, blank=True)
    billing_postal_code = models.CharField(max_length=20, blank=True)
    billing_country = models.CharField(max_length=100, blank=True)
    
    is_default = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    last_used = models.DateTimeField(null=True, blank=True)
    
    provider = models.CharField(max_length=50)  # paystack, crypto
    provider_payment_method_id = models.CharField(max_length=200)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-is_default', '-last_used']
        unique_together = ['user', 'provider_payment_method_id']
    
    def __str__(self):
        if self.payment_type == 'card':
            return f"Card ending in {self.card_last4}"
        elif self.payment_type in ['usdt_erc20', 'usdt_trc20', 'bitcoin', 'ethereum']:
            return f"{self.get_payment_type_display()} - {self.crypto_wallet_address[:10]}..."
        else:
            return f"{self.get_payment_type_display()} for {self.user.email}"
    
    def save(self, *args, **kwargs):
        if self.is_default:
            PaymentMethod.objects.filter(user=self.user, is_default=True).update(is_default=False)
        super().save(*args, **kwargs)


class CryptoTransaction(models.Model):
    """Track cryptocurrency transactions"""
    
    CRYPTO_TYPES = (
        ('usdt_erc20', 'USDT (ERC-20)'),
        ('usdt_trc20', 'USDT (TRC-20)'),
        ('bitcoin', 'Bitcoin'),
        ('ethereum', 'Ethereum'),
    )
    
    TRANSACTION_STATUS = (
        ('pending', 'Pending'),
        ('confirming', 'Confirming'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('expired', 'Expired'),
    )
    
    payment = models.OneToOneField(Payment, on_delete=models.CASCADE, related_name='crypto_details')
    crypto_type = models.CharField(max_length=20, choices=CRYPTO_TYPES)
    
    from_address = models.CharField(max_length=200)
    to_address = models.CharField(max_length=200)
    transaction_hash = models.CharField(max_length=200, unique=True, db_index=True)
    block_number = models.IntegerField(null=True, blank=True)
    block_hash = models.CharField(max_length=200, blank=True)
    
    crypto_amount = models.DecimalField(max_digits=20, decimal_places=8)
    usd_amount = models.DecimalField(max_digits=12, decimal_places=2)
    exchange_rate = models.DecimalField(max_digits=20, decimal_places=8)
    
    confirmations = models.IntegerField(default=0)
    required_confirmations = models.IntegerField(default=12)
    confirmation_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    network_fee = models.DecimalField(max_digits=20, decimal_places=8, default=0)
    gas_price = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    gas_used = models.IntegerField(null=True, blank=True)
    nonce = models.IntegerField(null=True, blank=True)
    
    status = models.CharField(max_length=20, choices=TRANSACTION_STATUS, default='pending')
    first_seen = models.DateTimeField(auto_now_add=True)
    last_checked = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    raw_transaction = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-first_seen']
        indexes = [
            models.Index(fields=['transaction_hash']),
            models.Index(fields=['status', 'confirmations']),
            models.Index(fields=['from_address', 'to_address']),
        ]
    
    def __str__(self):
        return f"{self.crypto_type} TX: {self.transaction_hash[:10]}..."
    
    def update_confirmations(self, confirmations):
        self.confirmations = confirmations
        self.confirmation_percentage = (confirmations / self.required_confirmations) * 100
        
        if confirmations >= self.required_confirmations:
            self.status = 'completed'
            self.completed_at = timezone.now()
            self.payment.mark_as_completed()
        
        self.save(update_fields=['confirmations', 'confirmation_percentage', 'status', 'completed_at'])


class RefundRequest(models.Model):
    """Refund requests from users"""
    
    REFUND_REASONS = (
        ('cancellation', 'Booking Cancellation'),
        ('service_issue', 'Service Issue'),
        ('payment_error', 'Payment Error'),
        ('duplicate', 'Duplicate Payment'),
        ('dissatisfied', 'Not Satisfied with Service'),
        ('other', 'Other'),
    )
    
    REFUND_STATUS = (
        ('pending', 'Pending Review'),
        ('approved', 'Approved'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('rejected', 'Rejected'),
        ('escalated', 'Escalated'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request_number = models.CharField(max_length=50, unique=True)
    
    user = models.ForeignKey('accounts.User', on_delete=models.PROTECT, related_name='refund_requests')
    booking = models.ForeignKey('bookings.Booking', on_delete=models.PROTECT, related_name='refund_requests')
    payment = models.ForeignKey(Payment, on_delete=models.PROTECT, related_name='refund_requests', null=True, blank=True)
    
    reason = models.CharField(max_length=30, choices=REFUND_REASONS)
    description = models.TextField()
    requested_amount = models.DecimalField(max_digits=12, decimal_places=2)
    approved_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    
    supporting_documents = models.FileField(upload_to='refund_documents/', blank=True)
    
    status = models.CharField(max_length=20, choices=REFUND_STATUS, default='pending')
    reviewed_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_refunds')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True)
    
    rejection_reason = models.TextField(blank=True)
    
    processed_at = models.DateTimeField(null=True, blank=True)
    processed_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='refund_requests_processed')
    refund_transaction_id = models.CharField(max_length=200, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['request_number']),
            models.Index(fields=['user', 'status']),
            models.Index(fields=['status', 'created_at']),
        ]
    
    def __str__(self):
        return f"Refund Request {self.request_number} - {self.user.email}"
    
    def save(self, *args, **kwargs):
        if not self.request_number:
            self.request_number = self.generate_request_number()
        super().save(*args, **kwargs)
    
    def generate_request_number(self):
        import random
        import string
        timestamp = timezone.now().strftime('%Y%m')
        random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        return f"REF{timestamp}{random_str}"
    
    def approve(self, amount, user, notes=""):
        self.status = 'approved'
        self.approved_amount = amount
        self.reviewed_by = user
        self.reviewed_at = timezone.now()
        self.review_notes = notes
        self.save(update_fields=['status', 'approved_amount', 'reviewed_by', 'reviewed_at', 'review_notes'])
        logger.info(f"Refund request {self.request_number} approved for ${amount}")
    
    def reject(self, reason, user):
        self.status = 'rejected'
        self.rejection_reason = reason
        self.reviewed_by = user
        self.reviewed_at = timezone.now()
        self.save(update_fields=['status', 'rejection_reason', 'reviewed_by', 'reviewed_at'])
        self.send_rejection_email()
        logger.info(f"Refund request {self.request_number} rejected: {reason}")
    
    def process_refund(self, transaction_id, user):
        self.status = 'completed'
        self.processed_at = timezone.now()
        self.processed_by = user
        self.refund_transaction_id = transaction_id
        self.save(update_fields=['status', 'processed_at', 'processed_by', 'refund_transaction_id'])
        
        if self.payment:
            self.payment.process_refund(self.approved_amount, self.reason, user)
        
        self.send_processed_email()
        logger.info(f"Refund request {self.request_number} processed with transaction {transaction_id}")
    
    def send_rejection_email(self):
        from django.core.mail import send_mail
        from django.template.loader import render_to_string
        
        subject = f"Refund Request Update - {self.request_number}"
        context = {'request': self, 'user': self.user, 'booking': self.booking}
        
        html_message = render_to_string('emails/refund_rejected.html', context)
        plain_message = render_to_string('emails/refund_rejected.txt', context)
        
        send_mail(
            subject,
            plain_message,
            'info@flynjet.com',
            [self.user.email],
            html_message=html_message,
            fail_silently=False,
        )
    
    def send_processed_email(self):
        from django.core.mail import send_mail
        from django.template.loader import render_to_string
        
        subject = f"Refund Processed - {self.request_number}"
        context = {'request': self, 'user': self.user, 'booking': self.booking}
        
        html_message = render_to_string('emails/refund_processed.html', context)
        plain_message = render_to_string('emails/refund_processed.txt', context)
        
        send_mail(
            subject,
            plain_message,
            'info@flynjet.com',
            [self.user.email],
            html_message=html_message,
            fail_silently=False,
        )


class Payout(models.Model):
    """Payouts to partners, agents, etc."""
    
    PAYOUT_STATUS = (
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payout_number = models.CharField(max_length=50, unique=True)
    
    recipient = models.ForeignKey('accounts.User', on_delete=models.PROTECT, related_name='payouts')
    recipient_type = models.CharField(max_length=20, choices=(
        ('agent', 'Agent'),
        ('partner', 'Partner'),
        ('vendor', 'Vendor'),
        ('pilot', 'Pilot'),
        ('crew', 'Crew'),
    ))
    
    amount_usd = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')
    exchange_rate = models.DecimalField(max_digits=10, decimal_places=6, default=1)
    amount_currency = models.DecimalField(max_digits=12, decimal_places=2)
    
    payout_method = models.CharField(max_length=20, choices=Payment.PAYMENT_METHODS)
    payout_details = models.JSONField(default=dict)
    
    related_bookings = models.ManyToManyField('bookings.Booking', blank=True)
    
    commission_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    commission_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    status = models.CharField(max_length=20, choices=PAYOUT_STATUS, default='pending')
    processed_at = models.DateTimeField(null=True, blank=True)
    processed_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='processed_payouts')
    
    provider = models.CharField(max_length=50)
    provider_payout_id = models.CharField(max_length=200, blank=True)
    provider_reference = models.CharField(max_length=200, blank=True)
    
    failure_reason = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Payout {self.payout_number} - {self.amount_usd} USD to {self.recipient.email}"
    
    def save(self, *args, **kwargs):
        if not self.payout_number:
            self.payout_number = self.generate_payout_number()
        super().save(*args, **kwargs)
    
    def generate_payout_number(self):
        import random
        import string
        timestamp = timezone.now().strftime('%Y%m')
        random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        return f"PO{timestamp}{random_str}"
    
    def mark_as_completed(self, provider_payout_id, provider_reference=''):
        self.status = 'completed'
        self.processed_at = timezone.now()
        self.provider_payout_id = provider_payout_id
        self.provider_reference = provider_reference
        self.save(update_fields=['status', 'processed_at', 'provider_payout_id', 'provider_reference'])
        logger.info(f"Payout {self.payout_number} completed")
    
    def mark_as_failed(self, reason):
        self.status = 'failed'
        self.failure_reason = reason
        self.save(update_fields=['status', 'failure_reason'])
        logger.error(f"Payout {self.payout_number} failed: {reason}")