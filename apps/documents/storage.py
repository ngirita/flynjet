import os
import hashlib
from django.core.files.storage import FileSystemStorage
from django.conf import settings
from django.utils import timezone

class DocumentStorage(FileSystemStorage):
    """Custom storage for documents with versioning"""
    
    def __init__(self, location=None, base_url=None):
        if location is None:
            location = os.path.join(settings.MEDIA_ROOT, 'documents')
        if base_url is None:
            base_url = '/media/documents/'
        super().__init__(location, base_url)
    
    def get_available_name(self, name, max_length=None):
        """Generate unique filename with timestamp"""
        if self.exists(name):
            # Add timestamp to filename
            base, ext = os.path.splitext(name)
            timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
            name = f"{base}_{timestamp}{ext}"
        return name
    
    def save(self, name, content, max_length=None):
        """Save file and calculate hash"""
        # Calculate file hash before saving
        if hasattr(content, 'read'):
            content.seek(0)
            file_hash = hashlib.sha256(content.read()).hexdigest()
            content.seek(0)
        else:
            file_hash = None
        
        # Save file
        saved_name = super().save(name, content, max_length)
        
        # Store hash in a separate file
        if file_hash:
            hash_path = f"{saved_name}.hash"
            with open(self.path(hash_path), 'w') as f:
                f.write(file_hash)
        
        return saved_name

class SecureDocumentStorage(DocumentStorage):
    """Secure storage with access control"""
    
    def __init__(self):
        super().__init__(
            location=os.path.join(settings.MEDIA_ROOT, 'secure_documents'),
            base_url='/media/secure_documents/'
        )
    
    def url(self, name):
        """Generate signed URL for secure access"""
        import time
        import hmac
        import hashlib
        import base64
        
        # Generate expiry timestamp (1 hour from now)
        expiry = int(time.time()) + 3600
        
        # Create signature
        message = f"{name}:{expiry}".encode()
        signature = hmac.new(
            settings.SECRET_KEY.encode(),
            message,
            hashlib.sha256
        ).digest()
        signature_b64 = base64.urlsafe_b64encode(signature).decode()
        
        # Return signed URL
        base_url = super().url(name)
        return f"{base_url}?expires={expiry}&signature={signature_b64}"