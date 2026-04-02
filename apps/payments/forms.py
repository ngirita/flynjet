from django import forms
from .models import Payment, RefundRequest

class PaymentForm(forms.ModelForm):
    payment_method = forms.ChoiceField(
        choices=Payment.PAYMENT_METHODS,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    save_payment_method = forms.BooleanField(required=False, initial=False)
    
    class Meta:
        model = Payment
        fields = ['payment_method']
    
    def clean(self):
        cleaned_data = super().clean()
        payment_method = cleaned_data.get('payment_method')
        
        if payment_method in ['visa', 'mastercard', 'amex']:
            # Validate card details are provided via Stripe
            if not self.data.get('payment_method_id'):
                raise forms.ValidationError("Payment method ID is required")
        
        return cleaned_data

class RefundRequestForm(forms.ModelForm):
    class Meta:
        model = RefundRequest
        fields = ['reason', 'description', 'supporting_documents']
        widgets = {
            'reason': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'supporting_documents': forms.FileInput(attrs={'class': 'form-control'})
        }