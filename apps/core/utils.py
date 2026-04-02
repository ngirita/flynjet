import hashlib
import random
import string
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings

def generate_unique_id(prefix='', length=12):
    """Generate a unique ID."""
    chars = string.ascii_uppercase + string.digits
    random_str = ''.join(random.choice(chars) for _ in range(length))
    return f"{prefix}{random_str}" if prefix else random_str

def generate_hash(data):
    """Generate SHA-256 hash of data."""
    return hashlib.sha256(str(data).encode()).hexdigest()

def send_template_email(subject, template_name, context, to_emails, from_email=None):
    """Send email using template."""
    if from_email is None:
        from_email = settings.DEFAULT_FROM_EMAIL
    
    html_message = render_to_string(f'emails/{template_name}.html', context)
    plain_message = render_to_string(f'emails/{template_name}.txt', context)
    
    send_mail(
        subject,
        plain_message,
        from_email,
        to_emails,
        html_message=html_message,
        fail_silently=False,
    )

def format_currency(amount, currency='USD'):
    """Format currency amount."""
    symbols = {
        'USD': '$',
        'EUR': '€',
        'GBP': '£',
        'AED': 'د.إ',
    }
    symbol = symbols.get(currency, '$')
    return f"{symbol}{amount:,.2f}"

def calculate_percentage(value, total):
    """Calculate percentage."""
    if total == 0:
        return 0
    return (value / total) * 100

def truncate_words(text, words=30):
    """Truncate text to specified number of words."""
    word_list = text.split()
    if len(word_list) <= words:
        return text
    return ' '.join(word_list[:words]) + '...'

def get_file_extension(filename):
    """Get file extension from filename."""
    return filename.split('.')[-1].lower() if '.' in filename else ''

def validate_file_size(file, max_size_mb=10):
    """Validate file size."""
    max_size_bytes = max_size_mb * 1024 * 1024
    return file.size <= max_size_bytes

def get_client_ip(request):
    """Get client IP from request."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

def get_user_agent(request):
    """Get user agent from request."""
    return request.META.get('HTTP_USER_AGENT', '')