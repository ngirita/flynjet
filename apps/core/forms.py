from django import forms
from django.core.mail import send_mail
from django.conf import settings
from .models import SupportTicket, FAQ
import logging

logger = logging.getLogger(__name__)

class ContactForm(forms.Form):
    """Contact form for website"""
    name = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'class': 'form-control'}))
    email = forms.EmailField(widget=forms.EmailInput(attrs={'class': 'form-control'}))
    subject = forms.CharField(max_length=200, widget=forms.TextInput(attrs={'class': 'form-control'}))
    message = forms.CharField(widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 5}))
    
    def send_email(self):
        """Send the contact form email to admin"""
        try:
            subject = f"Contact Form: {self.cleaned_data['subject']}"
            
            # Build email body
            email_body = f"""
Name: {self.cleaned_data['name']}
Email: {self.cleaned_data['email']}
Subject: {self.cleaned_data['subject']}

Message:
{self.cleaned_data['message']}

---
Sent from FlynJet Contact Form
            """
            
            send_mail(
                subject=subject,
                message=email_body,
                from_email=self.cleaned_data['email'],
                recipient_list=[settings.DEFAULT_FROM_EMAIL],
                fail_silently=False,
            )
            logger.info(f"Contact form email sent from {self.cleaned_data['email']}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send contact form email: {e}")
            return False

class SupportTicketForm(forms.ModelForm):
    """Form for creating support tickets"""
    class Meta:
        model = SupportTicket
        fields = ['category', 'subject', 'description', 'booking', 'attachments']
        widgets = {
            'category': forms.Select(attrs={'class': 'form-control'}),
            'subject': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
            'booking': forms.Select(attrs={'class': 'form-control'}),
            'attachments': forms.FileInput(attrs={'class': 'form-control'}),
        }