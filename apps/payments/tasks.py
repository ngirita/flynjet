from celery import shared_task
from django.utils import timezone
from .models import Payment, CryptoTransaction
from .crypto_utils import CryptoPaymentHandler
import logging

logger = logging.getLogger(__name__)

@shared_task
def process_pending_payments():
    """Process pending payments."""
    pending_payments = Payment.objects.filter(status='pending')
    
    for payment in pending_payments:
        if payment.created_at < timezone.now() - timezone.timedelta(hours=24):
            payment.status = 'failed'
            payment.failure_reason = 'Payment timeout'
            payment.save()
            logger.info(f"Payment {payment.id} timed out")
    
    return pending_payments.count()

@shared_task
def update_crypto_confirmations():
    """Update confirmations for crypto transactions."""
    crypto_handler = CryptoPaymentHandler()
    pending_txns = CryptoTransaction.objects.filter(status='pending')
    
    for txn in pending_txns:
        if txn.crypto_type in ['bitcoin', 'ethereum']:
            # Check blockchain for confirmations
            if txn.crypto_type == 'bitcoin':
                verified = crypto_handler.verify_bitcoin_payment(
                    txn.transaction_hash,
                    float(txn.crypto_amount)
                )
                if verified:
                    txn.update_confirmations(12)  # Assume confirmed
            elif txn.crypto_type == 'ethereum':
                # Check Ethereum confirmations
                pass
        
        txn.save()
    
    return pending_txns.count()

@shared_task
def process_refund_requests():
    """Process approved refund requests."""
    from .models import RefundRequest
    approved_requests = RefundRequest.objects.filter(
        status='approved',
        processed_at__isnull=True
    )
    
    for refund in approved_requests:
        if refund.payment:
            # Process refund through payment provider
            if refund.payment.provider == 'stripe':
                from .card_utils import CardPaymentHandler
                result = CardPaymentHandler.create_refund(
                    refund.payment.provider_payment_id,
                    float(refund.approved_amount)
                )
                if result['success']:
                    refund.process_refund(result['refund_id'], None)
                    logger.info(f"Refund {refund.id} processed")
    
    return approved_requests.count()

@shared_task
def update_exchange_rates():
    """Update cryptocurrency exchange rates."""
    from django.core.cache import cache
    crypto_handler = CryptoPaymentHandler()
    
    cryptos = ['bitcoin', 'ethereum', 'tether']
    for crypto in cryptos:
        rate = crypto_handler.get_crypto_exchange_rate(crypto)
        if rate:
            cache.set(f'exchange_rate_{crypto}_usd', rate, timeout=3600)
            logger.info(f"Updated {crypto} rate: {rate}")
    
    return len(cryptos)