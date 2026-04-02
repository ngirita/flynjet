# apps/payments/services/paystack_service.py - FIXED VERSION

import requests
import hmac
import hashlib
from django.conf import settings
import logging
from decimal import Decimal

logger = logging.getLogger(__name__)

class PaystackService:
    def __init__(self):
        self.secret_key = settings.PAYSTACK_SECRET_KEY
        self.public_key = settings.PAYSTACK_PUBLIC_KEY
        self.base_url = settings.PAYSTACK_PAYMENT_URL
        
        # DEBUG: Print the actual keys being loaded
        print("=" * 60)
        print("PAYSTACK SERVICE INITIALIZED")
        print(f"Secret Key from settings: {self.secret_key}")
        print(f"Secret Key length: {len(self.secret_key) if self.secret_key else 0}")
        print(f"Public Key from settings: {self.public_key}")
        print(f"Base URL: {self.base_url}")
        print("=" * 60)
        
        # FIX: Create an INSTANCE of the class (add parentheses)
        from ..exchange_utils import CurrencyExchangeService
        self.exchange_service = CurrencyExchangeService()  # <-- CRITICAL FIX: Added ()
        
        # Verify the instance is created correctly
        print(f"Exchange service instance created: {self.exchange_service}")
        print(f"Has convert_currency method: {hasattr(self.exchange_service, 'convert_currency')}")
        print("=" * 60)
    
    def convert_to_kes(self, amount, from_currency):
        """Convert any currency to KES using real exchange rates"""
        if from_currency == 'KES':
            return amount
        # Now this works because exchange_service is an instance
        return self.exchange_service.convert_currency(amount, from_currency, 'KES')
    
    def initialize_transaction(self, email, amount, reference, metadata=None, callback_url=None, currency='USD'):
        # DEBUG: Print the key being used for this request
        print(f"Using secret key for request: {self.secret_key[:20]}...")
        
        # Convert to KES for Paystack
        amount_kes = self.convert_to_kes(amount, currency)
        
        url = f"{self.base_url}/transaction/initialize"
        headers = {
            'Authorization': f'Bearer {self.secret_key}',
            'Content-Type': 'application/json',
        }
        
        payload = {
            'email': email,
            'amount': int(amount_kes * 100),  # Convert to kobo/cents
            'reference': reference,
            'currency': 'KES',  # Paystack requires KES for Kenyan merchants
            'callback_url': callback_url or settings.PAYSTACK_CALLBACK_URL,
            'metadata': {
                'original_amount': str(amount),
                'original_currency': currency,
                'converted_amount_kes': str(amount_kes),
                'exchange_rate': str(self.exchange_service.get_exchange_rate(currency, 'KES')),
                **(metadata or {})
            }
        }
        
        logger.info(f"Initializing Paystack transaction: {reference}")
        logger.info(f"{amount} {currency} -> KES {amount_kes}")
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            response_data = response.json()
            
            if response_data.get('status'):
                logger.info(f"Paystack transaction initialized: {reference}")
                return {
                    'success': True,
                    'authorization_url': response_data['data']['authorization_url'],
                    'access_code': response_data['data']['access_code'],
                    'reference': response_data['data']['reference'],
                    'original_amount': amount,
                    'original_currency': currency,
                    'amount_kes': amount_kes,
                    'message': 'Transaction initialized successfully'
                }
            else:
                logger.error(f"Paystack init failed: {response_data.get('message')}")
                return {
                    'success': False,
                    'message': response_data.get('message', 'Initialization failed')
                }
                
        except requests.exceptions.Timeout:
            logger.error("Paystack API timeout")
            return {
                'success': False,
                'message': 'Payment gateway timeout. Please try again.'
            }
        except requests.exceptions.ConnectionError:
            logger.error("Paystack connection error")
            return {
                'success': False,
                'message': 'Cannot connect to payment gateway. Check your internet connection.'
            }
        except Exception as e:
            logger.error(f"Paystack initialization error: {e}")
            return {
                'success': False,
                'message': 'Payment gateway connection error. Please try again.'
            }
    
    def verify_transaction(self, reference):
        """Verify a transaction with Paystack"""
        url = f"{self.base_url}/transaction/verify/{reference}"
        headers = {
            'Authorization': f'Bearer {self.secret_key}',
            'Content-Type': 'application/json',
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            response_data = response.json()
            
            if response_data.get('status'):
                data = response_data['data']
                
                if data['status'] == 'success':
                    amount_kes = data['amount'] / 100
                    metadata = data.get('metadata', {})
                    original_currency = metadata.get('original_currency', 'USD')
                    original_amount = Decimal(str(metadata.get('original_amount', amount_kes / 130)))
                    
                    return {
                        'success': True,
                        'original_amount': original_amount,
                        'original_currency': original_currency,
                        'amount_kes': amount_kes,
                        'currency': data['currency'],
                        'reference': data['reference'],
                        'payment_method': data.get('channel', 'card'),
                        'message': 'Transaction verified successfully'
                    }
                else:
                    return {
                        'success': False,
                        'message': f"Transaction status: {data['status']}"
                    }
            else:
                return {
                    'success': False,
                    'message': response_data.get('message', 'Verification failed')
                }
                
        except Exception as e:
            logger.error(f"Paystack verification error: {e}")
            return {
                'success': False,
                'message': 'Unable to verify transaction'
            }
    
    def create_refund(self, transaction_reference, amount=None, currency=None):
        """Create a refund with Paystack"""
        url = f"{self.base_url}/refund"
        headers = {
            'Authorization': f'Bearer {self.secret_key}',
            'Content-Type': 'application/json',
        }
        
        payload = {
            'transaction': transaction_reference,
        }
        
        if amount:
            if currency and currency != 'KES':
                amount_kes = self.convert_to_kes(amount, currency)
            else:
                amount_kes = amount
            payload['amount'] = int(amount_kes * 100)
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            response_data = response.json()
            
            if response_data.get('status'):
                logger.info(f"Refund created for {transaction_reference}")
                return {
                    'success': True,
                    'refund_id': response_data['data']['id'],
                    'status': response_data['data']['status'],
                    'message': 'Refund initiated successfully'
                }
            else:
                return {
                    'success': False,
                    'message': response_data.get('message', 'Refund failed')
                }
        except Exception as e:
            logger.error(f"Paystack refund error: {e}")
            return {
                'success': False,
                'message': str(e)
            }
    
    def list_banks(self):
        """Get list of banks for bank transfers"""
        url = f"{self.base_url}/bank"
        headers = {
            'Authorization': f'Bearer {self.secret_key}',
            'Content-Type': 'application/json',
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            response_data = response.json()
            
            if response_data.get('status'):
                return {
                    'success': True,
                    'banks': response_data['data']
                }
            return {'success': False, 'banks': []}
        except Exception as e:
            logger.error(f"Paystack list banks error: {e}")
            return {'success': False, 'banks': []}
    
    def create_transfer_recipient(self, name, account_number, bank_code, currency='KES'):
        """Create a transfer recipient for payouts"""
        url = f"{self.base_url}/transferrecipient"
        headers = {
            'Authorization': f'Bearer {self.secret_key}',
            'Content-Type': 'application/json',
        }
        
        payload = {
            'type': 'nuban',
            'name': name,
            'account_number': account_number,
            'bank_code': bank_code,
            'currency': currency,
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            response_data = response.json()
            
            if response_data.get('status'):
                return {
                    'success': True,
                    'recipient_code': response_data['data']['recipient_code'],
                    'message': 'Transfer recipient created successfully'
                }
            else:
                return {
                    'success': False,
                    'message': response_data.get('message', 'Failed to create recipient')
                }
        except Exception as e:
            logger.error(f"Paystack create recipient error: {e}")
            return {
                'success': False,
                'message': str(e)
            }
    
    def initiate_transfer(self, recipient_code, amount, reference, reason=''):
        """Initiate a transfer (payout)"""
        url = f"{self.base_url}/transfer"
        headers = {
            'Authorization': f'Bearer {self.secret_key}',
            'Content-Type': 'application/json',
        }
        
        payload = {
            'source': 'balance',
            'amount': int(amount * 100),  # Convert to kobo
            'recipient': recipient_code,
            'reference': reference,
            'reason': reason,
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            response_data = response.json()
            
            if response_data.get('status'):
                return {
                    'success': True,
                    'transfer_code': response_data['data']['transfer_code'],
                    'message': 'Transfer initiated successfully'
                }
            else:
                return {
                    'success': False,
                    'message': response_data.get('message', 'Transfer failed')
                }
        except Exception as e:
            logger.error(f"Paystack initiate transfer error: {e}")
            return {
                'success': False,
                'message': str(e)
            }
    
    def verify_webhook_signature(self, payload, signature):
        """Verify Paystack webhook signature"""
        expected_signature = hmac.new(
            self.secret_key.encode('utf-8'),
            payload,
            hashlib.sha512
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected_signature)