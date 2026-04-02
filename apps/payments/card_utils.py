# apps/payments/card_utils.py - CLEAN VERSION USING SERVICE LAYER

from django.conf import settings
from .services.paystack_service import PaystackService
import logging
import uuid

logger = logging.getLogger(__name__)


class CardPaymentHandler:
    """
    Card payment handler using Paystack's REAL API
    All API calls go through PaystackService for consistency
    """
    
    @staticmethod
    def create_payment_intent(amount_usd, currency='usd', metadata=None, email=None):
        """
        Create a payment intent with Paystack - REAL API call
        """
        if not email:
            raise ValueError("Email is required for Paystack payment")
        
        paystack = PaystackService()
        
        # Generate unique reference
        reference = f"PAY{uuid.uuid4().hex[:12].upper()}"
        
        # REAL Paystack API call via service
        result = paystack.initialize_transaction(
            email=email,
            amount=amount_usd,
            reference=reference,
            metadata=metadata or {}
        )
        
        if result['success']:
            logger.info(f"Payment intent created with Paystack: {reference}")
            return {
                'success': True,
                'client_secret': result['access_code'],
                'intent_id': result['reference'],
                'authorization_url': result['authorization_url']
            }
        else:
            logger.error(f"Failed to create payment intent: {result['message']}")
            return {
                'success': False,
                'error': result['message']
            }
    
    @staticmethod
    def confirm_payment(payment_intent_id):
        """
        Confirm/verify a payment with Paystack - REAL API call
        """
        paystack = PaystackService()
        
        # REAL Paystack API call to verify transaction
        result = paystack.verify_transaction(payment_intent_id)
        
        if result['success']:
            logger.info(f"Payment confirmed via Paystack: {payment_intent_id}")
            return {
                'success': True,
                'status': 'succeeded',
                'amount': result['amount'],
                'payment_method': result.get('payment_method', 'card')
            }
        else:
            logger.error(f"Payment confirmation failed: {result['message']}")
            return {
                'success': False,
                'error': result['message']
            }
    
    @staticmethod
    def create_refund(payment_intent_id, amount=None):
        """
        Create a refund with Paystack - REAL API call
        Uses PaystackService.create_refund() method
        """
        paystack = PaystackService()
        
        # REAL Paystack API call via service
        result = paystack.create_refund(payment_intent_id, amount)
        
        if result['success']:
            logger.info(f"Refund created for {payment_intent_id}")
            return {
                'success': True,
                'refund_id': result['refund_id'],
                'status': result['status'],
                'message': result['message']
            }
        else:
            logger.error(f"Refund failed: {result['message']}")
            return {
                'success': False,
                'error': result['message']
            }
    
    @staticmethod
    def save_payment_method(user, payment_method_id):
        """
        Save payment method for future use - REAL Paystack API
        Creates a customer in Paystack
        """
        paystack = PaystackService()
        
        # Paystack customer creation endpoint
        url = f"{paystack.base_url}/customer"
        headers = {
            'Authorization': f'Bearer {paystack.secret_key}',
            'Content-Type': 'application/json',
        }
        
        payload = {
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'phone': getattr(user, 'phone_number', ''),
        }
        
        try:
            import requests
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            response_data = response.json()
            
            if response_data.get('status'):
                return {
                    'success': True,
                    'customer_id': response_data['data']['customer_code'],
                    'message': 'Payment method saved with Paystack'
                }
            else:
                return {
                    'success': False,
                    'error': response_data.get('message', 'Failed to save payment method')
                }
        except Exception as e:
            logger.error(f"Save payment method error: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    def create_subscription(customer_id, price_id):
        """
        Create a subscription - REAL Paystack API
        """
        paystack = PaystackService()
        
        # Paystack subscription creation endpoint
        url = f"{paystack.base_url}/subscription"
        headers = {
            'Authorization': f'Bearer {paystack.secret_key}',
            'Content-Type': 'application/json',
        }
        
        payload = {
            'customer': customer_id,
            'plan': price_id,
        }
        
        try:
            import requests
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            response_data = response.json()
            
            if response_data.get('status'):
                return {
                    'success': True,
                    'subscription_id': response_data['data']['id'],
                    'client_secret': response_data['data']['subscription_code'],
                    'message': 'Subscription created successfully'
                }
            else:
                return {
                    'success': False,
                    'error': response_data.get('message', 'Subscription creation failed')
                }
        except Exception as e:
            logger.error(f"Subscription creation error: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    def verify_webhook_signature(payload, sig_header):
        """
        Verify Paystack webhook signature - REAL verification
        """
        paystack = PaystackService()
        is_valid = paystack.verify_webhook_signature(payload, sig_header)
        
        if is_valid:
            return {
                'success': True,
                'event': None  # Event will be parsed from payload
            }
        else:
            logger.error("Invalid Paystack webhook signature")
            return {
                'success': False,
                'error': 'Invalid signature'
            }