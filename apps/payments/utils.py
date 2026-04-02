import uuid
import hashlib
import hmac
from decimal import Decimal
from django.utils import timezone
from django.conf import settings

def generate_transaction_id(prefix='TXN'):
    """Generate unique transaction ID"""
    timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
    unique_id = uuid.uuid4().hex[:8].upper()
    return f"{prefix}{timestamp}{unique_id}"

def generate_refund_id(payment_id):
    """Generate refund ID from payment"""
    return f"REF{payment_id[-12:]}"

def calculate_fees(amount, payment_method):
    """Calculate processing fees based on payment method"""
    fees = {
        'card': Decimal('0.029'),  # 2.9% - Paystack
        'usdt_erc20': Decimal('0.01'),  # 1%
        'usdt_trc20': Decimal('0.005'),  # 0.5%
        'bitcoin': Decimal('0.02'),  # 2%
        'ethereum': Decimal('0.02'),  # 2%
        'bank_transfer': Decimal('0.005'),  # 0.5%
        'wire_transfer': Decimal('0.01'),  # 1%
    }
    
    fee_rate = fees.get(payment_method, Decimal('0.03'))
    processing_fee = amount * fee_rate
    
    if payment_method == 'card':
        processing_fee += Decimal('0.30')  # $0.30 fixed for Paystack
    
    return processing_fee.quantize(Decimal('0.01'))

def validate_card_number(card_number):
    """Validate credit card number using Luhn algorithm"""
    def digits_of(n):
        return [int(d) for d in str(n)]
    
    digits = digits_of(card_number)
    odd_digits = digits[-1::-2]
    even_digits = digits[-2::-2]
    checksum = sum(odd_digits)
    for d in even_digits:
        checksum += sum(digits_of(d * 2))
    
    return checksum % 10 == 0

def mask_card_number(card_number):
    """Mask credit card number for display"""
    if len(card_number) >= 4:
        return '*' * (len(card_number) - 4) + card_number[-4:]
    return card_number

def get_payment_method_icon(payment_method):
    """Get icon class for payment method"""
    icons = {
        'card': 'fas fa-credit-card',
        'usdt_erc20': 'fas fa-dollar-sign',
        'usdt_trc20': 'fas fa-dollar-sign',
        'bitcoin': 'fab fa-bitcoin',
        'ethereum': 'fab fa-ethereum',
        'bank_transfer': 'fas fa-university',
        'wire_transfer': 'fas fa-exchange-alt',
    }
    return icons.get(payment_method, 'fas fa-credit-card')

def format_currency(amount, currency='USD'):
    """Format currency amount"""
    symbols = {
        'USD': '$',
        'EUR': '€',
        'GBP': '£',
        'JPY': '¥',
        'AED': 'د.إ',
        'KES': 'KSh',
    }
    symbol = symbols.get(currency, '$')
    return f"{symbol}{amount:,.2f}"

def generate_payment_hash(payment_data):
    """Generate secure hash for payment verification"""
    data_string = f"{payment_data['amount']}{payment_data['user_id']}{payment_data['timestamp']}{settings.SECRET_KEY}"
    return hashlib.sha256(data_string.encode()).hexdigest()

def verify_payment_hash(payment_data, hash_to_verify):
    """Verify payment hash"""
    calculated_hash = generate_payment_hash(payment_data)
    return hmac.compare_digest(calculated_hash, hash_to_verify)

def get_exchange_rate(from_currency, to_currency):
    """Get exchange rate between currencies"""
    rates = {
        ('USD', 'EUR'): 0.85,
        ('USD', 'GBP'): 0.73,
        ('USD', 'JPY'): 110.0,
        ('USD', 'AED'): 3.67,
        ('USD', 'KES'): 128.50,
        ('EUR', 'USD'): 1.18,
        ('GBP', 'USD'): 1.37,
    }
    return rates.get((from_currency, to_currency), 1.0)

def calculate_refund_amount(payment_amount, cancellation_hours_before):
    """Calculate refund amount based on cancellation timing"""
    if cancellation_hours_before >= 48:
        return payment_amount
    elif cancellation_hours_before >= 24:
        return payment_amount * Decimal('0.5')
    else:
        return Decimal('0')

def generate_receipt_number(payment_id):
    """Generate receipt number"""
    timestamp = timezone.now().strftime('%Y%m')
    return f"RCPT{timestamp}{payment_id[-6:]}"

def validate_iban(iban):
    """Validate IBAN number"""
    iban = iban.replace(' ', '').upper()
    if not iban.isalnum():
        return False
    
    iban = iban[4:] + iban[:4]
    iban_numeric = ''
    for char in iban:
        if char.isalpha():
            iban_numeric += str(ord(char) - 55)
        else:
            iban_numeric += char
    
    return int(iban_numeric) % 97 == 1