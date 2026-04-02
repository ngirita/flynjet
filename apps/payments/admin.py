from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone  # ADDED
from django.contrib import messages  # ADDED
from .models import Payment, PaymentMethod, CryptoTransaction, RefundRequest, Payout
from apps.bookings.models import BookingHistory  # ADDED

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = [
        'transaction_id', 'user', 'booking', 'payment_method',
        'amount_usd', 'status', 'payment_date', 'receipt_link'
    ]
    list_filter = ['status', 'payment_method', 'payment_type', 'created_at']
    search_fields = ['transaction_id', 'user__email', 'booking__booking_reference']
    readonly_fields = ['transaction_id', 'created_at', 'updated_at']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Transaction Information', {
            'fields': ('transaction_id', 'user', 'booking', 'invoice')
        }),
        ('Payment Details', {
            'fields': (
                'payment_method', 'payment_type', 'status'
            )
        }),
        ('Amounts', {
            'fields': (
                'amount_usd', 'currency', 'exchange_rate', 'amount_currency',
                'processing_fee_usd', 'gateway_fee_usd', 'net_amount_usd'
            )
        }),
        ('Provider Details', {
            'fields': (
                'provider', 'provider_payment_id', 'provider_charge_id',
                'provider_customer_id'
            )
        }),
        ('Card Details', {
            'fields': (
                'card_last4', 'card_brand', 'card_expiry_month',
                'card_expiry_year', 'card_token'
            )
        }),
        ('Crypto Details', {
            'fields': (
                'crypto_wallet_address', 'crypto_transaction_hash',
                'crypto_network', 'crypto_confirmations',
                'crypto_required_confirmations'
            )
        }),
        ('Bank Details', {
            'fields': (
                'bank_name', 'bank_account_last4', 'bank_routing_number',
                'bank_reference'
            )
        }),
        ('Status Tracking', {
            'fields': ('payment_date', 'failure_reason', 'failure_code')
        }),
        ('Refund Details', {
            'fields': (
                'refund_amount_usd', 'refund_reason', 'refund_date',
                'refund_transaction_id', 'refunded_by'
            )
        }),
        ('Metadata', {
            'fields': ('ip_address', 'user_agent', 'metadata', 'receipt_url', 'receipt_sent'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    # UPDATED actions list - added confirm_payment
    actions = ['mark_as_completed', 'confirm_payment', 'process_refund', 'send_receipt']
    
    def receipt_link(self, obj):
        if obj.receipt_url:
            return format_html('<a href="{}" target="_blank">View Receipt</a>', obj.receipt_url)
        return "No receipt"
    receipt_link.short_description = "Receipt"
    
    def mark_as_completed(self, request, queryset):
        for payment in queryset:
            payment.mark_as_completed()
        self.message_user(request, f"{queryset.count()} payments marked as completed.")
    mark_as_completed.short_description = "Mark as completed"
    
    def process_refund(self, request, queryset):
        for payment in queryset:
            payment.process_refund(payment.amount_usd, "Admin refund", request.user)
        self.message_user(request, f"Refunds processed for {queryset.count()} payments.")
    process_refund.short_description = "Process full refund"
    
    def send_receipt(self, request, queryset):
        for payment in queryset:
            payment.send_receipt()
        self.message_user(request, f"Receipts sent for {queryset.count()} payments.")
    send_receipt.short_description = "Send receipt"

    def confirm_payment(self, request, queryset):
        """Admin action to manually confirm bank/crypto payments"""
        # Import the correct function from signals
        from .signals import send_payment_confirmation_with_attachments  # FIXED
        
        count = 0
        for payment in queryset:
            if payment.status != 'completed':
                payment.status = 'completed'
                payment.payment_date = timezone.now()
                payment.save()
                
                booking = payment.booking
                
                # Update booking to paid
                booking.status = 'paid'
                booking.payment_status = 'paid'
                booking.amount_paid = payment.amount_usd
                booking.amount_due = booking.total_amount_usd - payment.amount_usd
                booking.paid_at = timezone.now()
                booking.save()
                
                # Add to history
                BookingHistory.objects.create(
                    booking=booking,
                    old_status='pending',
                    new_status='paid',
                    changed_by=request.user,
                    reason=f'Payment confirmed by admin: {payment.get_payment_method_display()}'
                )
                
                # Generate and send documents using the correct function
                send_payment_confirmation_with_attachments(booking, payment)  # FIXED
                
                count += 1
                self.message_user(request, f'Payment {payment.transaction_id} confirmed. Documents sent to {booking.user.email}')
        
        if count > 0:
            self.message_user(request, f'{count} payment(s) confirmed successfully')

    confirm_payment.short_description = "Confirm selected payments (bank/crypto)"

@admin.register(RefundRequest)
class RefundRequestAdmin(admin.ModelAdmin):
    list_display = [
        'request_number', 'user', 'booking', 'reason',
        'requested_amount', 'status', 'created_at'
    ]
    list_filter = ['status', 'reason', 'created_at']
    search_fields = ['request_number', 'user__email', 'booking__booking_reference']
    readonly_fields = ['request_number', 'created_at', 'updated_at']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Request Information', {
            'fields': ('request_number', 'user', 'booking', 'payment')
        }),
        ('Request Details', {
            'fields': ('reason', 'description', 'requested_amount', 'approved_amount')
        }),
        ('Documents', {
            'fields': ('supporting_documents',)
        }),
        ('Status Tracking', {
            'fields': (
                'status', 'reviewed_by', 'reviewed_at', 'review_notes',
                'rejection_reason'
            )
        }),
        ('Processing', {
            'fields': ('processed_at', 'processed_by', 'refund_transaction_id')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['approve_requests', 'reject_requests', 'process_approved']
    
    def approve_requests(self, request, queryset):
        for refund in queryset:
            refund.approve(refund.requested_amount, request.user, "Approved by admin")
        self.message_user(request, f"{queryset.count()} refund requests approved.")
    approve_requests.short_description = "Approve selected requests"
    
    def reject_requests(self, request, queryset):
        for refund in queryset:
            refund.reject("Rejected by admin", request.user)
        self.message_user(request, f"{queryset.count()} refund requests rejected.")
    reject_requests.short_description = "Reject selected requests"
    
    def process_approved(self, request, queryset):
        for refund in queryset.filter(status='approved'):
            refund.process_refund(f"REF-{refund.request_number}", request.user)
        self.message_user(request, f"Processed refunds for {queryset.count()} requests.")
    process_approved.short_description = "Process approved refunds"

    