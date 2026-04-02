from django import forms
from .models import Review

class MultipleFileInput(forms.ClearableFileInput):
    """Custom widget to support multiple file uploads"""
    allow_multiple_selected = True

class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = [
            'review_type', 'title', 'content',
            'overall_rating', 'punctuality_rating', 'comfort_rating',
            'service_rating', 'value_rating', 'cleanliness_rating'
        ]
        widgets = {
            'review_type': forms.Select(attrs={'class': 'form-control'}),
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Summary of your experience'}),
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'placeholder': 'Share your experience...'}),
            'overall_rating': forms.NumberInput(attrs={'class': 'form-control rating-input', 'min': 1, 'max': 5}),
            'punctuality_rating': forms.NumberInput(attrs={'class': 'form-control rating-input', 'min': 1, 'max': 5}),
            'comfort_rating': forms.NumberInput(attrs={'class': 'form-control rating-input', 'min': 1, 'max': 5}),
            'service_rating': forms.NumberInput(attrs={'class': 'form-control rating-input', 'min': 1, 'max': 5}),
            'value_rating': forms.NumberInput(attrs={'class': 'form-control rating-input', 'min': 1, 'max': 5}),
            'cleanliness_rating': forms.NumberInput(attrs={'class': 'form-control rating-input', 'min': 1, 'max': 5}),
        }


class ReviewPhotoForm(forms.Form):
    """Form for uploading multiple photos with a review"""
    photos = forms.ImageField(
        widget=MultipleFileInput(attrs={'multiple': True, 'class': 'form-control'}),
        required=False
    )
    
    def clean_photos(self):
        """Validate uploaded photos"""
        photos = self.files.getlist('photos')
        if photos:
            # Optional: Limit number of photos
            if len(photos) > 10:
                raise forms.ValidationError('You can upload a maximum of 10 photos.')
            
            # Optional: Validate file sizes
            for photo in photos:
                if photo.size > 5 * 1024 * 1024:  # 5MB limit
                    raise forms.ValidationError(f'Photo {photo.name} exceeds 5MB limit.')
        
        return photos