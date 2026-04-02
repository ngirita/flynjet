import json
import hmac
import hashlib
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.conf import settings
from .models import Payment, CryptoTransaction  # ← ADD CryptoTransaction import
import stripe
import logging

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def stripe_webhook(request):
    """Handle Stripe webhook events"""
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        # Invalid payload
        logger.error("Invalid Stripe webhook payload")
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError:
        # Invalid signature
        logger.error("Invalid Stripe webhook signature")
        return HttpResponse(status=400)
    
    # Handle the event
    if event['type'] == 'payment_intent.succeeded':
        payment_intent = event['data']['object']
        handle_payment_succeeded(payment_intent)
    
    elif event['type'] == 'payment_intent.payment_failed':
        payment_intent = event['data']['object']
        handle_payment_failed(payment_intent)
    
    elif event['type'] == 'charge.refunded':
        charge = event['data']['object']
        handle_refund(charge)
    
    elif event['type'] == 'charge.dispute.created':
        dispute = event['data']['object']
        handle_dispute_created(dispute)
    
    elif event['type'] == 'customer.subscription.created':
        subscription = event['data']['object']
        handle_subscription_created(subscription)
    
    elif event['type'] == 'customer.subscription.updated':
        subscription = event['data']['object']
        handle_subscription_updated(subscription)
    
    elif event['type'] == 'customer.subscription.deleted':
        subscription = event['data']['object']
        handle_subscription_deleted(subscription)
    
    return HttpResponse(status=200)


def handle_payment_succeeded(payment_intent):
    """Handle successful payment"""
    try:
        payment = Payment.objects.get(provider_payment_id=payment_intent['id'])
        payment.mark_as_completed()
        logger.info(f"Payment {payment.id} completed via webhook")
    except Payment.DoesNotExist:
        logger.error(f"Payment not found for intent {payment_intent['id']}")


def handle_payment_failed(payment_intent):
    """Handle failed payment"""
    try:
        payment = Payment.objects.get(provider_payment_id=payment_intent['id'])
        error_message = payment_intent.get('last_payment_error', {}).get('message', 'Payment failed')
        payment.mark_as_failed(error_message)
        logger.info(f"Payment {payment.id} failed via webhook")
    except Payment.DoesNotExist:
        logger.error(f"Payment not found for intent {payment_intent['id']}")


def handle_refund(charge):
    """Handle refund"""
    try:
        payment = Payment.objects.get(provider_charge_id=charge['id'])
        refund_amount = charge['amount_refunded'] / 100  # Convert from cents
        payment.process_refund(refund_amount, 'Refunded via webhook', None)
        logger.info(f"Refund processed for payment {payment.id}")
    except Payment.DoesNotExist:
        logger.error(f"Payment not found for charge {charge['id']}")


def handle_dispute_created(dispute):
    """Handle dispute created"""
    try:
        payment = Payment.objects.get(provider_charge_id=dispute['charge'])
        payment.status = 'disputed'
        payment.save()
        
        # Create dispute record
        from apps.disputes.models import Dispute
        Dispute.objects.create(
            user=payment.user,
            booking=payment.booking,
            payment=payment,
            dispute_type='chargeback',
            disputed_amount=dispute['amount'] / 100,
            subject='Chargeback Dispute',
            description=dispute.get('reason', 'Chargeback filed')
        )
        
        logger.info(f"Dispute created for payment {payment.id}")
    except Payment.DoesNotExist:
        logger.error(f"Payment not found for charge {dispute['charge']}")


def handle_subscription_created(subscription):
    """Handle subscription created"""
    logger.info(f"Subscription created: {subscription['id']}")


def handle_subscription_updated(subscription):
    """Handle subscription updated"""
    logger.info(f"Subscription updated: {subscription['id']}")


def handle_subscription_deleted(subscription):
    """Handle subscription deleted"""
    logger.info(f"Subscription deleted: {subscription['id']}")


@csrf_exempt
@require_POST
def coinbase_webhook(request):
    """Handle Coinbase Commerce webhook events"""
    payload = request.body
    signature = request.META.get('HTTP_X_CC_WEBHOOK_SIGNATURE')
    
    # Verify signature
    expected_signature = hmac.new(
        settings.COINBASE_WEBHOOK_SECRET.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    
    if not hmac.compare_digest(signature, expected_signature):
        logger.error("Invalid Coinbase webhook signature")
        return HttpResponse(status=400)
    
    event = json.loads(payload)
    
    if event['event']['type'] == 'charge:confirmed':
        handle_coinbase_charge_confirmed(event['event']['data'])
    
    elif event['event']['type'] == 'charge:failed':
        handle_coinbase_charge_failed(event['event']['data'])
    
    elif event['event']['type'] == 'charge:delayed':
        handle_coinbase_charge_delayed(event['event']['data'])
    
    return HttpResponse(status=200)


def handle_coinbase_charge_confirmed(charge_data):
    """Handle confirmed Coinbase charge"""
    try:
        crypto_txn = CryptoTransaction.objects.get(
            transaction_hash=charge_data['code'],
            status='confirming'
        )
        crypto_txn.update_confirmations(12)
        logger.info(f"Crypto transaction {crypto_txn.id} confirmed")
    except CryptoTransaction.DoesNotExist:
        logger.error(f"Crypto transaction not found for charge {charge_data['code']}")


def handle_coinbase_charge_failed(charge_data):
    """Handle failed Coinbase charge"""
    try:
        crypto_txn = CryptoTransaction.objects.get(
            transaction_hash=charge_data['code'],
            status='pending'
        )
        crypto_txn.status = 'failed'
        crypto_txn.save()
        
        # Update payment
        if crypto_txn.payment:
            crypto_txn.payment.mark_as_failed("Crypto payment failed")
        logger.info(f"Crypto transaction {crypto_txn.id} failed")
    except CryptoTransaction.DoesNotExist:
        logger.error(f"Crypto transaction not found for charge {charge_data['code']}")


def handle_coinbase_charge_delayed(charge_data):
    """Handle delayed Coinbase charge"""
    try:
        crypto_txn = CryptoTransaction.objects.get(
            transaction_hash=charge_data['code'],
            status='pending'
        )
        crypto_txn.status = 'confirming'
        crypto_txn.save()
        logger.info(f"Crypto transaction {crypto_txn.id} delayed, now confirming")
    except CryptoTransaction.DoesNotExist:
        logger.error(f"Crypto transaction not found for charge {charge_data['code']}")