from django import forms
from .models import Dispute, DisputeMessage, DisputeEvidence

class DisputeForm(forms.ModelForm):
    class Meta:
        model = Dispute
        fields = ['dispute_type', 'subject', 'description']
        widgets = {
            'dispute_type': forms.Select(attrs={'class': 'form-control'}),
            'subject': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Brief subject line'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'placeholder': 'Describe the issue in detail...'}),
        }


class DisputeMessageForm(forms.ModelForm):
    class Meta:
        model = DisputeMessage
        fields = ['message', 'attachment']
        widgets = {
            'message': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Type your message...'}),
            'attachment': forms.FileInput(attrs={'class': 'form-control'}),
        }


class DisputeEvidenceForm(forms.ModelForm):
    class Meta:
        model = DisputeEvidence
        fields = ['evidence_type', 'file', 'description']
        widgets = {
            'evidence_type': forms.Select(attrs={'class': 'form-control'}),
            'file': forms.FileInput(attrs={'class': 'form-control'}),
            'description': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Brief description'}),
        }