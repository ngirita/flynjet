import hashlib
import hmac
import base64
import re
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class DataEncryption:
    """Handle data encryption for sensitive information"""
    
    def __init__(self):
        self.key = self._derive_key(settings.SECRET_KEY)
        self.cipher = Fernet(self.key)
    
    def _derive_key(self, password: str, salt: bytes = None) -> bytes:
        """Derive encryption key from password"""
        if salt is None:
            salt = b'flynjet_salt'  # In production, use random salt per encryption
        
        kdf = PBKDF2(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key
    
    def encrypt(self, data: str) -> str:
        """Encrypt data"""
        if not data:
            return data
        
        try:
            encrypted = self.cipher.encrypt(data.encode())
            return base64.urlsafe_b64encode(encrypted).decode()
        except Exception as e:
            logger.error(f"Encryption error: {e}")
            raise
    
    def decrypt(self, encrypted_data: str) -> str:
        """Decrypt data"""
        if not encrypted_data:
            return encrypted_data
        
        try:
            decoded = base64.urlsafe_b64decode(encrypted_data.encode())
            decrypted = self.cipher.decrypt(decoded)
            return decrypted.decode()
        except Exception as e:
            logger.error(f"Decryption error: {e}")
            raise
    
    def hash_data(self, data: str) -> str:
        """Create a one-way hash of data (for passwords, etc.)"""
        salt = settings.SECRET_KEY
        return hashlib.pbkdf2_hmac(
            'sha256',
            data.encode(),
            salt.encode(),
            100000
        ).hex()


class FieldEncryption:
    """Descriptor for automatic field encryption"""
    
    def __init__(self, field_name):
        self.field_name = field_name
        self.encryptor = DataEncryption()
    
    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        
        encrypted_value = obj.__dict__.get(f"_{self.field_name}")
        if encrypted_value:
            return self.encryptor.decrypt(encrypted_value)
        return None
    
    def __set__(self, obj, value):
        if value is None:
            obj.__dict__[f"_{self.field_name}"] = None
        else:
            encrypted = self.encryptor.encrypt(str(value))
            obj.__dict__[f"_{self.field_name}"] = encrypted


class SecureStorage:
    """Secure storage for sensitive files"""
    
    @staticmethod
    def encrypt_file(file_content):
        """Encrypt file content"""
        encryptor = DataEncryption()
        return encryptor.encrypt(file_content)
    
    @staticmethod
    def decrypt_file(encrypted_content):
        """Decrypt file content"""
        encryptor = DataEncryption()
        return encryptor.decrypt(encrypted_content)
    
    @staticmethod
    def verify_file_integrity(file_content, expected_hash):
        """Verify file integrity using SHA-256"""
        actual_hash = hashlib.sha256(file_content).hexdigest()
        return hmac.compare_digest(actual_hash, expected_hash)


class PIIDetector:
    """Detect Personally Identifiable Information in text"""
    
    PII_PATTERNS = {
        'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        'phone': r'\b\+?[\d\s-]{10,}\b',
        'ssn': r'\b\d{3}-\d{2}-\d{4}\b',
        'credit_card': r'\b(?:\d{4}[-\s]?){3}\d{4}\b',
        'passport': r'\b[A-Z]{1,2}\d{6,9}\b',
        'address': r'\d+\s+[A-Za-z\s]+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr)\b'
    }
    
    @classmethod
    def detect_pii(cls, text):
        """Detect PII in text"""
        import re
        findings = []
        
        for pii_type, pattern in cls.PII_PATTERNS.items():
            matches = re.findall(pattern, text)
            for match in matches:
                findings.append({
                    'type': pii_type,
                    'value': match,
                    'position': text.find(match)
                })
        
        return findings
    
    @classmethod
    def redact_pii(cls, text):
        """Redact PII from text"""
        import re
        
        redacted = text
        for pii_type, pattern in cls.PII_PATTERNS.items():
            redacted = re.sub(pattern, f'[REDACTED {pii_type.upper()}]', redacted)
        
        return redacted


class DataMasking:
    """Mask sensitive data for display"""
    
    @staticmethod
    def mask_email(email):
        """Mask email address (j***@example.com)"""
        if not email or '@' not in email:
            return email
        
        local, domain = email.split('@')
        if len(local) <= 2:
            masked_local = local[0] + '*' * len(local[1:])
        else:
            masked_local = local[0] + '*' * (len(local) - 2) + local[-1]
        
        return f"{masked_local}@{domain}"
    
    @staticmethod
    def mask_phone(phone):
        """Mask phone number (***-***-1234)"""
        if not phone:
            return phone
        
        # Keep last 4 digits
        cleaned = re.sub(r'\D', '', phone)
        if len(cleaned) >= 4:
            return '*' * (len(cleaned) - 4) + cleaned[-4:]
        return '*' * len(cleaned)
    
    @staticmethod
    def mask_credit_card(card_number):
        """Mask credit card number (****-****-****-1234)"""
        if not card_number:
            return card_number
        
        cleaned = re.sub(r'\D', '', card_number)
        if len(cleaned) >= 4:
            return '*' * (len(cleaned) - 4) + cleaned[-4:]
        return '*' * len(cleaned)
    
    @staticmethod
    def mask_passport(passport):
        """Mask passport number (AB*****6)"""
        if not passport:
            return passport
        
        if len(passport) >= 4:
            return passport[:2] + '*' * (len(passport) - 3) + passport[-1]
        return '*' * len(passport)