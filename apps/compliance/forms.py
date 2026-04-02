from django import forms
from .models import DataSubjectRequest, DataProcessingAgreement, BreachNotification

class ConsentForm(forms.Form):
    """Form for managing consent"""
    CONSENT_CHOICES = (
        ('terms', 'Terms of Service'),
        ('privacy', 'Privacy Policy'),
        ('marketing', 'Marketing Communications'),
        ('cookies', 'Cookie Consent'),
        ('data_processing', 'Data Processing'),
    )
    
    consent_type = forms.ChoiceField(choices=CONSENT_CHOICES)
    granted = forms.BooleanField(required=False)
    version = forms.CharField(max_length=20, initial='1.0')


class DataSubjectRequestForm(forms.ModelForm):
    """Form for data subject requests"""
    class Meta:
        model = DataSubjectRequest
        fields = ['request_type', 'description']
        widgets = {
            'request_type': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }


class DataProcessingAgreementForm(forms.ModelForm):
    """Form for data processing agreements (admin)"""
    class Meta:
        model = DataProcessingAgreement
        fields = '__all__'
        widgets = {
            'signed_date': forms.DateInput(attrs={'type': 'date'}),
            'effective_date': forms.DateInput(attrs={'type': 'date'}),
            'expiry_date': forms.DateInput(attrs={'type': 'date'}),
        }


class BreachNotificationForm(forms.ModelForm):
    """Form for breach notifications (admin)"""
    class Meta:
        model = BreachNotification
        fields = '__all__'
        widgets = {
            'detected_at': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }