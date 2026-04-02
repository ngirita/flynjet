import ssl
import certifi
from django.core.mail.backends.smtp import EmailBackend

class SSLFixedEmailBackend(EmailBackend):
    """Email backend with proper SSL certificate handling"""
    
    def open(self):
        if self.connection:
            return False
            
        try:
            # Create SSL context with certifi certificates
            ssl_context = ssl.create_default_context(cafile=certifi.where())
            
            self.connection = self.connection_class(
                self.host, self.port,
                local_hostname=self.local_hostname,
                timeout=self.timeout,
                certfile=self.certfile,
                keyfile=self.keyfile,
                ssl_context=ssl_context
            )
            self.connection.ehlo()
            if self.username and self.password:
                self.connection.login(self.username, self.password)
            return True
        except Exception:
            if not self.fail_silently:
                raise
            return False