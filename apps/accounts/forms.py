from django import forms
from django.contrib.auth.forms import PasswordChangeForm
from django.core.exceptions import ValidationError
from .models import User, UserProfile, UserSecuritySettings
import re

class UserRegistrationForm(forms.ModelForm):
    password1 = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        min_length=12
    )
    password2 = forms.CharField(
        label='Confirm Password',
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )
    
    class Meta:
        model = User
        fields = ['email', 'first_name', 'last_name', 'phone_number']
        widgets = {
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def clean_password1(self):
        password = self.cleaned_data.get('password1')
        
        # Password validation
        if len(password) < 12:
            raise ValidationError('Password must be at least 12 characters.')
        if not re.search(r'[A-Z]', password):
            raise ValidationError('Password must contain at least one uppercase letter.')
        if not re.search(r'[a-z]', password):
            raise ValidationError('Password must contain at least one lowercase letter.')
        if not re.search(r'[0-9]', password):
            raise ValidationError('Password must contain at least one number.')
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            raise ValidationError('Password must contain at least one special character.')
        
        return password

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')
        
        if password1 and password2 and password1 != password2:
            raise ValidationError('Passwords do not match.')
        
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password1'])
        user.username = user.email.split('@')[0]  # Generate username from email
        
        if commit:
            user.save()
        return user

class UserLoginForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'form-control-custom', 'placeholder': 'Enter your email'})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control-custom', 'placeholder': 'Enter your password'})
    )
    remember_me = forms.BooleanField(required=False, initial=True)
    two_factor_method = forms.ChoiceField(
        choices=[
            ('email', 'Email OTP'),
            ('authenticator', 'Authenticator App'),
        ],
        required=False,
        initial='email',
        widget=forms.RadioSelect(attrs={'class': 'two-factor-options'})
    )
    otp_code = forms.CharField(
        required=False,
        max_length=6,
        min_length=6,
        widget=forms.TextInput(attrs={'class': 'form-control text-center', 'placeholder': 'Enter OTP'})
    )    

class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = [
            'profile_image', 'gender', 'nationality', 'passport_number',
            'passport_expiry', 'frequent_flyer_number', 'preferred_airport',
            'emergency_contact_name', 'emergency_contact_phone',
            'emergency_contact_relation', 'dietary_restrictions',
            'medical_conditions', 'special_assistance_required',
            'seat_preference', 'meal_preference'
        ]
        widgets = {
            'profile_image': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),  # Add this
            'dietary_restrictions': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'medical_conditions': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }


class TwoFactorSetupForm(forms.Form):
    code = forms.CharField(
        max_length=6,
        min_length=6,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '6-digit code'})
    )


class TwoFactorVerifyForm(forms.Form):
    code = forms.CharField(
        max_length=6,
        min_length=6,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '6-digit code'})
    )

# Add these to your existing forms.py file

class PasswordResetRequestForm(forms.Form):
    """
    Form for requesting a password reset.
    """
    email = forms.EmailField(
        label='Email Address',
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your email address'
        })
    )

    def clean_email(self):
        email = self.cleaned_data.get('email')
        try:
            user = User.objects.get(email=email)
            if not user.is_active:
                raise ValidationError('This account is inactive.')
        except User.DoesNotExist:
            # Don't reveal that email doesn't exist for security
            pass
        return email


class SetPasswordForm(forms.Form):
    """
    Form for setting a new password after reset.
    """
    new_password1 = forms.CharField(
        label='New Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter new password'
        }),
        min_length=12
    )
    new_password2 = forms.CharField(
        label='Confirm New Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm new password'
        })
    )

    def clean_new_password1(self):
        password = self.cleaned_data.get('new_password1')
        
        # Password validation
        if len(password) < 12:
            raise ValidationError('Password must be at least 12 characters.')
        if not re.search(r'[A-Z]', password):
            raise ValidationError('Password must contain at least one uppercase letter.')
        if not re.search(r'[a-z]', password):
            raise ValidationError('Password must contain at least one lowercase letter.')
        if not re.search(r'[0-9]', password):
            raise ValidationError('Password must contain at least one number.')
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            raise ValidationError('Password must contain at least one special character.')
        
        return password

    def clean(self):
        cleaned_data = super().clean()
        new_password1 = cleaned_data.get('new_password1')
        new_password2 = cleaned_data.get('new_password2')
        
        if new_password1 and new_password2 and new_password1 != new_password2:
            raise ValidationError('Passwords do not match.')
        
        return cleaned_data


class ResendVerificationForm(forms.Form):
    """
    Form for resending verification email.
    """
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your email address'
        })
    )


class PasswordChangeCustomForm(forms.Form):
    """
    Form for changing password when logged in.
    """
    old_password = forms.CharField(
        label='Current Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter current password'
        })
    )
    new_password1 = forms.CharField(
        label='New Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter new password'
        }),
        min_length=12
    )
    new_password2 = forms.CharField(
        label='Confirm New Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm new password'
        })
    )

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_old_password(self):
        old_password = self.cleaned_data.get('old_password')
        if not self.user.check_password(old_password):
            raise ValidationError('Current password is incorrect.')
        return old_password

    def clean_new_password1(self):
        password = self.cleaned_data.get('new_password1')
        
        # Password validation
        if len(password) < 12:
            raise ValidationError('Password must be at least 12 characters.')
        if not re.search(r'[A-Z]', password):
            raise ValidationError('Password must contain at least one uppercase letter.')
        if not re.search(r'[a-z]', password):
            raise ValidationError('Password must contain at least one lowercase letter.')
        if not re.search(r'[0-9]', password):
            raise ValidationError('Password must contain at least one number.')
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            raise ValidationError('Password must contain at least one special character.')
        
        return password

    def clean(self):
        cleaned_data = super().clean()
        new_password1 = cleaned_data.get('new_password1')
        new_password2 = cleaned_data.get('new_password2')
        
        if new_password1 and new_password2 and new_password1 != new_password2:
            raise ValidationError('New passwords do not match.')
        
        return cleaned_data