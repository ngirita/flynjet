import re
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

class UppercaseValidator:
    """Validate that password contains at least one uppercase letter."""
    
    def validate(self, password, user=None):
        if not re.findall('[A-Z]', password):
            raise ValidationError(
                _("The password must contain at least one uppercase letter."),
                code='password_no_upper',
            )
    
    def get_help_text(self):
        return _("Your password must contain at least one uppercase letter.")

class LowercaseValidator:
    """Validate that password contains at least one lowercase letter."""
    
    def validate(self, password, user=None):
        if not re.findall('[a-z]', password):
            raise ValidationError(
                _("The password must contain at least one lowercase letter."),
                code='password_no_lower',
            )
    
    def get_help_text(self):
        return _("Your password must contain at least one lowercase letter.")

class NumberValidator:
    """Validate that password contains at least one number."""
    
    def validate(self, password, user=None):
        if not re.findall('[0-9]', password):
            raise ValidationError(
                _("The password must contain at least one number."),
                code='password_no_number',
            )
    
    def get_help_text(self):
        return _("Your password must contain at least one number.")

class SymbolValidator:
    """Validate that password contains at least one special character."""
    
    def validate(self, password, user=None):
        if not re.findall('[()[\]{}|\\`~!@#$%^&*_\-+=;:\'",<>./?]', password):
            raise ValidationError(
                _("The password must contain at least one special character."),
                code='password_no_symbol',
            )
    
    def get_help_text(self):
        return _("Your password must contain at least one special character.")

def validate_phone_number(value):
    """Validate phone number format."""
    phone_regex = re.compile(r'^\+?1?\d{9,15}$')
    if not phone_regex.match(value):
        raise ValidationError(
            _('Phone number must be entered in format: "+999999999". Up to 15 digits allowed.'),
            code='invalid_phone'
        )

def validate_iata_code(value):
    """Validate IATA airport code format."""
    if not re.match(r'^[A-Z]{3}$', value):
        raise ValidationError(
            _('IATA code must be exactly 3 uppercase letters.'),
            code='invalid_iata'
        )

def validate_passport_number(value):
    """Validate passport number format."""
    if not re.match(r'^[A-Z0-9]{6,12}$', value):
        raise ValidationError(
            _('Passport number must be 6-12 alphanumeric characters.'),
            code='invalid_passport'
        )

def validate_future_date(value):
    """Validate that date is in the future."""
    from django.utils import timezone
    if value <= timezone.now().date():
        raise ValidationError(
            _('Date must be in the future.'),
            code='past_date'
        )

def validate_positive_number(value):
    """Validate that number is positive."""
    if value <= 0:
        raise ValidationError(
            _('Value must be positive.'),
            code='non_positive'
        )