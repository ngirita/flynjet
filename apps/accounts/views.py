from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import CreateView, TemplateView, UpdateView, FormView, View, ListView
from django.contrib import messages
from django.urls import reverse_lazy
from django.utils import timezone
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.db.models import Sum
from django.http import JsonResponse
from django.core.mail import send_mail, EmailMultiAlternatives 
import secrets
import pyotp
import qrcode
import io
import base64
import random
from .models import User, UserProfile, EmailVerification, PasswordReset, UserSecuritySettings, LoginHistory, EmailOTP
from .forms import (
    UserRegistrationForm, UserLoginForm, UserProfileForm,
    PasswordResetRequestForm, SetPasswordForm, TwoFactorSetupForm,
    TwoFactorVerifyForm, ResendVerificationForm, PasswordChangeCustomForm
)
import logging
logger = logging.getLogger(__name__)

# apps/accounts/views.py - Update RegisterView

class RegisterView(CreateView):
    model = User
    form_class = UserRegistrationForm
    template_name = 'accounts/register.html'
    success_url = reverse_lazy('accounts:login')

    def form_valid(self, form):
        response = super().form_valid(form)
        user = form.save()
        
        # Create email verification token
        token = secrets.token_urlsafe(32)
        EmailVerification.objects.create(
            user=user,
            token=token,
            expires_at=timezone.now() + timezone.timedelta(hours=24)
        )
        
        # Send verification email
        verification_url = f"{settings.SITE_URL}/accounts/verify-email/{token}/"
        html_message = render_to_string('accounts/emails/verify_email.html', {
            'user': user,
            'verification_url': verification_url
        })
        
        send_mail(
            'Verify your email - FlynJet',
            f'Please verify your email: {verification_url}',
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            html_message=html_message,
            fail_silently=False,
        )
        
        messages.success(self.request, 'Registration successful! Please check your email to verify your account.')
        
        # ========== CHECK FOR PENDING CONTRACT ==========
        if 'pending_contract_token' in self.request.session:
            token = self.request.session['pending_contract_token']
            # Clear session data
            if 'pending_contract_token' in self.request.session:
                del self.request.session['pending_contract_token']
            if 'pending_action' in self.request.session:
                del self.request.session['pending_action']
            if 'signup_prefill' in self.request.session:
                del self.request.session['signup_prefill']
            
            # Log the user in
            login(self.request, user)
            
            # Redirect to contract payment
            return redirect('payments:contract_payment', token=token)
        
        return response


# apps/accounts/views.py - Complete LoginView with pending contract handling

class LoginView(FormView):
    form_class = UserLoginForm
    template_name = 'accounts/login.html'

    def get(self, request, *args, **kwargs):
        # Check if user is already authenticated
        if request.user.is_authenticated:
            # Check for pending contract first
            if 'pending_contract_token' in request.session:
                token = request.session['pending_contract_token']
                # Clear session data
                for key in ['pending_contract_token', 'pending_action', 'pending_contract_email']:
                    if key in request.session:
                        del request.session[key]
                return redirect('payments:contract_payment', token=token)
            
            next_url = request.GET.get('next')
            if next_url:
                return redirect(next_url)
            if request.user.user_type == 'admin' or request.user.is_staff:
                return redirect('admin:index')
            return redirect('core:home')
        
        # Check if we're in the middle of 2FA verification
        if '2fa_user_id' in request.session:
            return redirect('accounts:2fa_verify')
        
        # Clear stale OTP sessions
        if 'otp_email' in request.session:
            if 'otp_created_at' in request.session:
                created_at = request.session.get('otp_created_at')
                if created_at and (timezone.now().timestamp() - created_at) > 600:
                    self.clear_otp_session(request)
            else:
                self.clear_otp_session(request)
        
        # Show OTP verification page if we have an OTP email in session
        if 'otp_email' in request.session:
            # Check if this was a fallback from authenticator
            context = self.get_context_data()
            context['otp_method'] = request.session.get('otp_method', 'email')
            return render(request, 'accounts/otp_verify.html', context)
        else:
            return super().get(request, *args, **kwargs)
        
    def clear_otp_session(self, request):
        """Clear OTP-related session data."""
        for key in ['otp_email', 'otp_user_id', 'otp_remember_me', 'otp_next_url', 'otp_id', 'otp_created_at']:
            if key in request.session:
                del request.session[key]

    def get_success_url(self):
        # Check for pending contract first
        if 'pending_contract_token' in self.request.session:
            token = self.request.session['pending_contract_token']
            # Clear session data
            for key in ['pending_contract_token', 'pending_action', 'pending_contract_email']:
                if key in self.request.session:
                    del self.request.session[key]
            return reverse_lazy('payments:contract_payment', kwargs={'token': token})
        
        next_url = self.request.GET.get('next')
        if next_url:
            return next_url
        if hasattr(self.request, 'user') and self.request.user.is_authenticated:
            if self.request.user.user_type == 'admin' or self.request.user.is_staff:
                return reverse_lazy('admin:index')
        return reverse_lazy('core:home')

    def post(self, request, *args, **kwargs):
        """Handle POST requests - separate OTP verification from login"""
        # If we have OTP in session, we're verifying OTP
        if 'otp_email' in request.session:
            otp_code = request.POST.get('otp_code')
            if not otp_code:
                messages.error(request, 'Please enter the OTP code.')
                return redirect('accounts:login')
            
            # Verify OTP
            return self.verify_otp_code(request, otp_code)
        
        # Otherwise, process normal login
        form = self.get_form()
        if form.is_valid():
            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    def verify_otp_code(self, request, otp_code):
        """Verify the OTP code"""
        email = request.session.get('otp_email')
        stored_otp_id = request.session.get('otp_id')
        
        logger.debug(f"Verifying OTP - Code: {otp_code}, Email: {email}, Stored ID: {stored_otp_id}")
        
        if not email:
            messages.error(request, 'Session expired. Please login again.')
            self.clear_otp_session(request)
            return redirect('accounts:login')
        
        try:
            user = User.objects.get(email=email)
            
            # Try to find the OTP - first by ID if available, then by code
            otp = None
            
            if stored_otp_id:
                try:
                    otp = EmailOTP.objects.get(
                        id=stored_otp_id,
                        user=user,
                        is_used=False,
                        expires_at__gt=timezone.now()
                    )
                    logger.debug(f"Found OTP by ID: {otp.id}, Code in DB: {otp.code}")
                except EmailOTP.DoesNotExist:
                    logger.debug("OTP not found by ID, trying by code...")
            
            if not otp:
                otp = EmailOTP.objects.filter(
                    user=user,
                    code=otp_code,
                    is_used=False,
                    expires_at__gt=timezone.now()
                ).first()
                
                if otp:
                    logger.debug(f"Found OTP by code: {otp.id}")
                else:
                    logger.debug("No valid OTP found")
            
            if not otp:
                messages.error(request, 'Invalid or expired OTP code. Please request a new code.')
                self.clear_otp_session(request)
                return redirect('accounts:login')
            
            if otp.code != otp_code:
                logger.debug(f"Code mismatch - DB: {otp.code}, Input: {otp_code}")
                messages.error(request, 'Invalid OTP code. Please try again.')
                return redirect('accounts:login')
            
            # Mark OTP as used
            otp.is_used = True
            otp.save()
            logger.debug(f"OTP {otp.id} marked as used")
            
            # Set the backend attribute on the user
            user.backend = 'django.contrib.auth.backends.ModelBackend'
            
            # Login the user
            login(request, user)
            
            # Set session expiry
            remember_me = request.session.get('otp_remember_me', False)
            if not remember_me:
                request.session.set_expiry(0)
            
            # Record login
            user.record_login(request)
            
            # Clear OTP session
            self.clear_otp_session(request)
            
            # ========== CHECK FOR PENDING CONTRACT ==========
            if 'pending_contract_token' in request.session:
                token = request.session['pending_contract_token']
                # Clear session data
                for key in ['pending_contract_token', 'pending_action', 'pending_contract_email']:
                    if key in request.session:
                        del request.session[key]
                
                messages.success(request, f'Welcome back, {user.get_full_name()}!')
                return redirect('payments:contract_payment', token=token)
            
            # Get next URL
            next_url = request.GET.get('next')
            if not next_url:
                if user.user_type == 'admin' or user.is_staff:
                    next_url = reverse_lazy('admin:index')
                else:
                    next_url = reverse_lazy('core:home')
            
            messages.success(request, f'Welcome back, {user.get_full_name()}!')
            return redirect(next_url)
            
        except User.DoesNotExist:
            logger.error(f"User not found: {email}")
            self.clear_otp_session(request)
            messages.error(request, 'User not found.')
            return redirect('accounts:login')
        except Exception as e:
            logger.error(f"OTP verification error: {e}", exc_info=True)
            self.clear_otp_session(request)
            messages.error(request, 'Error verifying OTP. Please try again.')
            return redirect('accounts:login')

    def form_valid(self, form):
        """Handle normal login form submission (email and password)"""
        email = form.cleaned_data.get('email')
        password = form.cleaned_data.get('password')
        remember_me = form.cleaned_data.get('remember_me', False)
        two_factor_method = form.cleaned_data.get('two_factor_method', 'email')
        
        logger.debug(f"Processing login for email: {email} with 2FA method: {two_factor_method}")
        
        # Authenticate user
        user = authenticate(self.request, email=email, password=password)
        
        if user is not None:
            logger.debug(f"User authenticated: {user.email}")
            
            if user.is_account_locked():
                messages.error(self.request, 'Account is locked. Please try again later.')
                return self.form_invalid(form)
            
            # Store which authentication backend was used
            auth_backend = getattr(user, 'backend', 'django.contrib.auth.backends.ModelBackend')
            
            # Check if user has authenticator 2FA enabled
            has_authenticator = user.security_settings.two_factor_enabled
            
            # Determine which 2FA method to use based on user selection and availability
            if has_authenticator and two_factor_method == 'authenticator':
                # User has authenticator enabled AND selected it - use authenticator
                logger.debug(f"User {user.email} using authenticator 2FA")
                self.request.session['2fa_user_id'] = str(user.id)
                self.request.session['2fa_remember_me'] = remember_me
                self.request.session['2fa_next_url'] = self.request.GET.get('next')
                self.request.session['auth_backend'] = auth_backend
                
                messages.info(self.request, 'Please enter your authenticator code to continue.')
                return redirect('accounts:2fa_verify')
            else:
                # User either:
                # 1. Selected email OTP (regardless of whether they have authenticator)
                # 2. Selected authenticator but doesn't have it enabled
                # 3. Doesn't have authenticator enabled at all
                # In all these cases, use email OTP
                if has_authenticator and two_factor_method == 'authenticator':
                    # User selected authenticator but it's not enabled
                    messages.warning(self.request, 'Authenticator app is not set up for your account. Please set it up in security settings first, or use Email OTP.')
                
                logger.debug(f"User {user.email} using email OTP")
                return self.send_email_otp(user, remember_me, auth_backend)
                
        else:
            logger.debug("Authentication failed")
            messages.error(self.request, 'Invalid email or password.')
            return self.form_invalid(form)
    
    def send_email_otp(self, user, remember_me, auth_backend):
        """Send email OTP and set up session"""
        # Clear any old OTPs for this user
        EmailOTP.objects.filter(user=user, is_used=False).delete()
        
        # Clear any existing OTP session data
        self.clear_otp_session(self.request)
        
        # Generate OTP
        otp_code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
        logger.debug(f"Generated OTP: {otp_code}")
        
        # Save OTP
        otp = EmailOTP.objects.create(
            user=user,
            code=otp_code,
            expires_at=timezone.now() + timezone.timedelta(minutes=10)
        )
        
        # Send OTP email
        try:
            subject = 'Your OTP Code - FlynJet'
            email_context = {
                'user': user,
                'otp_code': otp_code,
                'expires_in': 10,
                'site_url': settings.SITE_URL,
            }

            text_content = render_to_string('accounts/emails/otp_email.txt', email_context)
            html_content = render_to_string('accounts/emails/otp_email.html', email_context)

            msg = EmailMultiAlternatives(subject, text_content, settings.DEFAULT_FROM_EMAIL, [user.email])
            msg.attach_alternative(html_content, "text/html")
            msg.send()
            logger.debug(f"OTP email sent to {user.email}")
        except Exception as e:
            logger.error(f"Failed to send OTP email: {e}")
            messages.error(self.request, 'Failed to send OTP. Please try again.')
            return self.form_invalid(self.get_form())

        # Store in session
        self.request.session['otp_email'] = user.email
        self.request.session['otp_user_id'] = str(user.id)
        self.request.session['otp_remember_me'] = remember_me
        self.request.session['otp_next_url'] = self.request.GET.get('next')
        self.request.session['otp_id'] = str(otp.id)
        self.request.session['otp_created_at'] = timezone.now().timestamp()
        self.request.session['auth_backend'] = auth_backend
        self.request.session['otp_method'] = 'email'  # Store the method used
        
        logger.debug(f"Session stored - OTP ID: {otp.id}")
        
        messages.info(self.request, f'OTP sent to {user.email}. Please check your email.')
        return redirect('accounts:login')  # This will show the OTP verification page
    
    def form_invalid(self, form):
        return self.render_to_response(self.get_context_data(form=form))                   
     
class ResendOTPView(View):
    """View to resend OTP code during login."""
    
    def get(self, request, *args, **kwargs):
        # Check if OTP email exists in session
        if 'otp_email' not in request.session:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': 'No active OTP session'}, status=400)
            messages.error(request, 'No active OTP session found.')
            return redirect('accounts:login')
        
        email = request.session.get('otp_email')
        
        try:
            user = User.objects.get(email=email)
            
            # Delete old unused OTPs for this user
            EmailOTP.objects.filter(user=user, is_used=False).delete()
            
            # Generate new OTP code
            otp_code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
            logger.debug(f"Resending OTP: {otp_code}")
            
            # Save OTP
            otp = EmailOTP.objects.create(
                user=user,
                code=otp_code,
                expires_at=timezone.now() + timezone.timedelta(minutes=10)
            )
            
            # Send OTP email
            subject = 'Your OTP Code - FlynJet'
            email_context = {
                'user': user,
                'otp_code': otp_code,
                'expires_in': 10,
                'site_url': settings.SITE_URL,
            }

            text_content = render_to_string('accounts/emails/otp_email.txt', email_context)
            html_content = render_to_string('accounts/emails/otp_email.html', email_context)

            msg = EmailMultiAlternatives(subject, text_content, settings.DEFAULT_FROM_EMAIL, [user.email])
            msg.attach_alternative(html_content, "text/html")
            msg.send()
            
            # Update session with new OTP ID
            request.session['otp_id'] = str(otp.id)
            request.session['otp_created_at'] = timezone.now().timestamp()
            
            logger.debug(f"New OTP sent - ID: {otp.id}")
            
            # Check if AJAX request
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'message': f'New OTP sent to {user.email}'})
            
            messages.success(request, f'New OTP sent to {user.email}. Please check your email.')
            return redirect('accounts:login')
            
        except User.DoesNotExist:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': 'User not found'}, status=404)
            messages.error(request, 'User not found.')
            return redirect('accounts:login')
        except Exception as e:
            logger.error(f"Failed to resend OTP: {e}", exc_info=True)
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': str(e)}, status=500)
            messages.error(request, 'Failed to send OTP. Please try again.')
            return redirect('accounts:login')
                    
class VerifyEmailView(TemplateView):
    template_name = 'accounts/verify_email.html'

    def get(self, request, *args, **kwargs):
        token = kwargs.get('token')
        try:
            verification = EmailVerification.objects.get(token=token)
            if verification.is_valid():
                verification.verify()
                messages.success(request, 'Email verified successfully! You can now login.')
            else:
                messages.error(request, 'Verification link has expired.')
        except EmailVerification.DoesNotExist:
            messages.error(request, 'Invalid verification link.')
        
        return redirect('accounts:login')



class ProfileView(LoginRequiredMixin, TemplateView):
    template_name = 'accounts/profile.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Import inside method to avoid circular imports
        from django.db.models import Sum
        from decimal import Decimal
        
        # Calculate total spent from bookings amount_paid
        total_spent = user.bookings.aggregate(
            total=Sum('amount_paid')
        )['total'] or Decimal('0')
        
        context.update({
            'user': user,
            'bookings': user.bookings.order_by('-created_at')[:5],
            'total_spent': total_spent,
        })
        return context
        
class EditProfileView(LoginRequiredMixin, UpdateView):
    """
    View for editing user profile with proper image handling.
    """
    model = UserProfile
    form_class = UserProfileForm
    template_name = 'accounts/edit_profile.html'
    success_url = reverse_lazy('accounts:profile')

    def get_object(self, queryset=None):
        return self.request.user.profile

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['user'] = self.request.user
        return context

    def form_valid(self, form):
        """
        Handle the form submission with file upload.
        """
        try:
            # Get the profile instance
            profile = form.save(commit=False)
            
            # Handle profile image upload
            if 'profile_image' in self.request.FILES:
                profile_image = self.request.FILES['profile_image']
                
                # Validate file size (max 5MB)
                if profile_image.size > 5 * 1024 * 1024:
                    messages.error(self.request, 'Profile image must be less than 5MB.')
                    return self.form_invalid(form)
                
                # Validate file type
                allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
                if profile_image.content_type not in allowed_types:
                    messages.error(self.request, 'Please upload a valid image file (JPEG, PNG, GIF, or WebP).')
                    return self.form_invalid(form)
                
                # Save the image - the ProcessedImageField will handle the processing
                profile.profile_image = profile_image
            
            # Save the profile
            profile.save()
            form.save_m2m()  # Save many-to-many relationships if any
            
            # Force refresh to ensure we have the latest data
            profile.refresh_from_db()
            
            messages.success(self.request, 'Your profile has been updated successfully!')
            
            # Log the action
            logger.info(f"User {self.request.user.email} updated their profile. Image updated: {bool(profile_image)}")
            
            return super().form_valid(form)
            
        except Exception as e:
            logger.error(f"Error updating profile for {self.request.user.email}: {str(e)}")
            messages.error(self.request, f'Error updating profile: {str(e)}')
            return self.form_invalid(form)

    def form_invalid(self, form):
        """
        Handle invalid form submission.
        """
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(self.request, f'{field}: {error}')
        return super().form_invalid(form)

class SecuritySettingsView(LoginRequiredMixin, TemplateView):
    """
    View for security settings (2FA, password change)
    """
    template_name = 'accounts/security.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['user'] = self.request.user
        context['security_settings'] = self.request.user.security_settings
        context['two_factor_form'] = TwoFactorSetupForm()
        context['password_form'] = PasswordChangeCustomForm(user=self.request.user)
        
        # Check if we're in setup mode
        setup_mode = self.request.session.get('setup_2fa_mode', False)
        context['setup_mode'] = setup_mode
        
        # Only generate QR code and backup codes if 2FA is not enabled AND we're in setup mode
        if not self.request.user.security_settings.two_factor_enabled and setup_mode:
            # Generate new secret if needed
            security = self.request.user.security_settings
            if not security.two_factor_secret:
                security.generate_2fa_secret()
            
            context['qr_code'] = security.generate_2fa_qr_code()
            context['backup_codes'] = security.generate_backup_codes()
        
        return context
    
    def post(self, request, *args, **kwargs):
        # Handle 2FA enable/disable
        if 'enable_2fa' in request.POST:
            return self.enable_2fa(request)
        elif 'disable_2fa' in request.POST:
            return self.disable_2fa(request)
        elif 'change_password' in request.POST:
            return self.change_password(request)
        elif 'setup_2fa' in request.POST:
            # User clicked "Set Up 2FA" button
            request.session['setup_2fa_mode'] = True
            return redirect('accounts:security_settings')
        elif 'cancel_setup' in request.POST:
            # User cancelled 2FA setup
            if 'setup_2fa_mode' in request.session:
                del request.session['setup_2fa_mode']
            return redirect('accounts:security_settings')
        
        return redirect('accounts:security_settings')
    
    def enable_2fa(self, request):
        code = request.POST.get('code')
        security = request.user.security_settings
        
        if security.verify_2fa_code(code):
            security.two_factor_enabled = True
            security.save()
            # Clear setup mode
            if 'setup_2fa_mode' in request.session:
                del request.session['setup_2fa_mode']
            messages.success(request, 'Two-factor authentication enabled successfully!')
        else:
            messages.error(request, 'Invalid verification code. Please make sure you entered the correct code from your authenticator app.')
        
        return redirect('accounts:security_settings')
    
    def disable_2fa(self, request):
        code = request.POST.get('code')
        security = request.user.security_settings
        
        if security.verify_2fa_code(code):
            security.two_factor_enabled = False
            security.two_factor_secret = ''
            security.two_factor_backup_codes = []
            security.save()
            messages.success(request, 'Two-factor authentication disabled successfully.')
        else:
            messages.error(request, 'Invalid verification code.')
        
        return redirect('accounts:security_settings')
    
    def change_password(self, request):
        form = PasswordChangeCustomForm(user=request.user, data=request.POST)
        
        if form.is_valid():
            user = request.user
            user.set_password(form.cleaned_data['new_password1'])
            user.save()
            
            # Update security settings
            security = user.security_settings
            security.password_changed_at = timezone.now()
            security.add_to_password_history(user.password)
            security.save()
            
            messages.success(request, 'Your password has been changed successfully! Please login again.')
            logout(request)
            return redirect('accounts:login')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, error)
        
        return redirect('accounts:security_settings')
    
class TwoFactorSetupView(LoginRequiredMixin, TemplateView):
    template_name = 'accounts/2fa_setup.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        security = self.request.user.security_settings
        context['qr_code'] = security.generate_2fa_qr_code()
        context['backup_codes'] = security.generate_backup_codes()
        return context

    def post(self, request, *args, **kwargs):
        code = request.POST.get('code')
        if request.user.security_settings.verify_2fa_code(code):
            request.user.security_settings.two_factor_enabled = True
            request.user.security_settings.save()
            messages.success(request, 'Two-factor authentication enabled successfully!')
            return redirect('accounts:security_settings')
        else:
            messages.error(request, 'Invalid verification code.')
            return self.get(request, *args, **kwargs)

# Add these to your existing views.py file

class PasswordResetRequestView(FormView):
    """
    View for requesting a password reset.
    """
    template_name = 'accounts/password_reset.html'
    form_class = PasswordResetRequestForm
    success_url = reverse_lazy('accounts:password_reset_done')

    def form_valid(self, form):
        email = form.cleaned_data['email']
        
        try:
            user = User.objects.get(email=email)
            
            # Generate reset token
            token = secrets.token_urlsafe(32)
            PasswordReset.objects.create(
                user=user,
                token=token,
                expires_at=timezone.now() + timezone.timedelta(hours=1),
                ip_address=self.request.META.get('REMOTE_ADDR', ''),
                user_agent=self.request.META.get('HTTP_USER_AGENT', '')
            )
            
            # Build the reset URL
            reset_url = f"{settings.SITE_URL}/auth/password-reset/{token}/"
            
            # Prepare context for the email template
            context = {
                'user': user,
                'reset_url': reset_url,
                'protocol': 'https' if self.request.is_secure() else 'http',
                'domain': self.request.get_host(),
                'site_name': 'FlynJet',
                'token': token,
                'expiry_hours': 24,  # You can make this configurable
            }
            
            # Render HTML email
            html_message = render_to_string('accounts/emails/password_reset.html', context)
            
            # Send email
            send_mail(
                'Password Reset Request - FlynJet',
                f'Click here to reset your password: {reset_url}',
                settings.DEFAULT_FROM_EMAIL,
                [email],
                html_message=html_message,
                fail_silently=False,
            )
            
        except User.DoesNotExist:
            # Don't reveal that user doesn't exist
            pass
        
        return super().form_valid(form)
    

class PasswordResetDoneView(TemplateView):
    """
    View shown after password reset email is sent.
    """
    template_name = 'accounts/password_reset_done.html'


class PasswordResetConfirmView(FormView):
    """
    View for confirming password reset with token.
    """
    template_name = 'accounts/password_reset_confirm.html'
    form_class = SetPasswordForm
    success_url = reverse_lazy('accounts:password_reset_complete')

    def dispatch(self, request, *args, **kwargs):
        token = kwargs.get('token')
        try:
            self.reset = PasswordReset.objects.get(token=token)
            if not self.reset.is_valid():
                messages.error(request, 'This password reset link has expired.')
                return redirect('accounts:password_reset')
        except PasswordReset.DoesNotExist:
            messages.error(request, 'Invalid password reset link.')
            return redirect('accounts:password_reset')
        
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['validlink'] = True
        context['token'] = self.kwargs.get('token')
        return context

    def form_valid(self, form):
        try:
            if self.reset.is_valid():
                user = self.reset.user
                user.set_password(form.cleaned_data['new_password1'])
                user.save()
                
                # Mark reset as used
                self.reset.mark_used()
                
                # Update security settings
                security = user.security_settings
                security.password_changed_at = timezone.now()
                security.add_to_password_history(user.password)
                security.save()
                
                messages.success(self.request, 'Your password has been reset successfully. You can now login with your new password.')
            else:
                messages.error(self.request, 'This password reset link has expired.')
                return redirect('accounts:password_reset')
                
        except PasswordReset.DoesNotExist:
            messages.error(self.request, 'Invalid password reset link.')
            return redirect('accounts:password_reset')
        
        return super().form_valid(form)

class PasswordResetCompleteView(TemplateView):
    """
    View shown after password reset is complete.
    """
    template_name = 'accounts/password_reset_complete.html'


class ResendVerificationView(FormView):
    """
    View for resending verification email.
    """
    template_name = 'accounts/resend_verification.html'
    form_class = ResendVerificationForm
    success_url = reverse_lazy('accounts:login')

    def form_valid(self, form):
        email = form.cleaned_data['email']
        
        try:
            user = User.objects.get(email=email)
            
            if user.email_verified:
                messages.info(self.request, 'This email is already verified. Please login.')
                return redirect('accounts:login')
            
            # Create new verification token
            token = secrets.token_urlsafe(32)
            EmailVerification.objects.create(
                user=user,
                token=token,
                expires_at=timezone.now() + timezone.timedelta(hours=24)
            )
            
            # Send verification email
            verification_url = f"{settings.SITE_URL}/accounts/verify-email/{token}/"
            html_message = render_to_string('accounts/emails/verify_email.html', {
                'user': user,
                'verification_url': verification_url
            })
            
            send_mail(
                'Verify your email - FlynJet',
                f'Please verify your email: {verification_url}',
                settings.DEFAULT_FROM_EMAIL,
                [email],
                html_message=html_message,
                fail_silently=False,
            )
            
            messages.success(self.request, 'Verification email sent. Please check your inbox.')
            
        except User.DoesNotExist:
            # Don't reveal that user doesn't exist
            messages.success(self.request, 'If this email exists, a verification link has been sent.')
        
        return super().form_valid(form)


class PasswordChangeView(LoginRequiredMixin, FormView):
    """
    View for changing password when logged in.
    """
    template_name = 'accounts/password_change.html'
    form_class = PasswordChangeCustomForm
    success_url = reverse_lazy('accounts:profile')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        user = self.request.user
        user.set_password(form.cleaned_data['new_password1'])
        user.save()
        
        # Update security settings
        security = user.security_settings
        security.password_changed_at = timezone.now()
        security.add_to_password_history(user.password)
        security.save()
        
        messages.success(self.request, 'Your password has been changed successfully.')
        return super().form_valid(form)

class LogoutView(LoginRequiredMixin, View):
    """
    Enhanced logout view with session cleanup and logging.
    """
    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            # Store user info before logout
            user = request.user
            ip_address = self.get_client_ip(request)
            user_agent = request.META.get('HTTP_USER_AGENT', '')
            
            # Clear all sessions for this user (optional - for security)
            self.clear_user_sessions(user)
            
            # Update last activity
            user.last_activity = timezone.now()
            user.save(update_fields=['last_activity'])
            
            # Create logout history
            from .models import LoginHistory
            LoginHistory.objects.create(
                user=user,
                ip_address=ip_address,
                user_agent=user_agent,
                login_type='logout',
                success=True
            )
            
            # Clear any 2FA session data
            if '2fa_user_id' in request.session:
                del request.session['2fa_user_id']
            
            # Perform logout
            logout(request)
            
            messages.success(request, 'You have been successfully logged out.')
        
        return redirect('core:home')  # or 'accounts:login'
    
    def post(self, request, *args, **kwargs):
        return self.get(request, *args, **kwargs)
    
    def get_client_ip(self, request):
        """Get client IP from request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def clear_user_sessions(self, user):
        """Clear all sessions for a user (optional security feature)."""
        from django.contrib.sessions.models import Session
        from django.utils import timezone
        
        # Get all sessions
        sessions = Session.objects.filter(expire_date__gte=timezone.now())
        
        for session in sessions:
            try:
                data = session.get_decoded()
                if data.get('_auth_user_id') == str(user.id):
                    session.delete()
            except:
                pass

# ===== TWO-FACTOR AUTHENTICATION VIEWS =====
class TwoFactorAuthView(FormView):
    """
    View for verifying 2FA code during login (including social login).
    """
    template_name = 'accounts/2fa_verify.html'
    form_class = TwoFactorVerifyForm

    def dispatch(self, request, *args, **kwargs):
        # Check if user_id is in session
        if '2fa_user_id' not in request.session:
            messages.error(request, 'No 2FA session found. Please login again.')
            return redirect('accounts:login')
        
        try:
            self.user = User.objects.get(id=request.session['2fa_user_id'])
        except User.DoesNotExist:
            messages.error(request, 'Invalid user session. Please login again.')
            return redirect('accounts:login')
        
        # Get the stored backend from session
        self.auth_backend = request.session.get('auth_backend', 'django.contrib.auth.backends.ModelBackend')
        
        # Check if this is a social login
        self.is_social_login = request.session.get('2fa_social_login', False)
        self.social_provider = request.session.get('2fa_social_provider', None)
        
        # Store the next URL
        self.next_url = request.session.get('2fa_next_url') or request.GET.get('next', '/')
        
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        """Return the stored next URL or home"""
        return self.next_url if hasattr(self, 'next_url') else reverse_lazy('core:home')

    def form_valid(self, form):
        code = form.cleaned_data['code']
        
        # Check backup codes first
        if code in self.user.security_settings.two_factor_backup_codes:
            self.user.security_settings.two_factor_backup_codes.remove(code)
            self.user.security_settings.save()
            verified = True
        else:
            # Verify TOTP code
            verified = self.user.security_settings.verify_2fa_code(code)
        
        if verified:
            # CRITICAL: Set the backend attribute on the user
            # This must match the backend that was used during authentication
            self.user.backend = self.auth_backend
            
            # Complete login
            if self.is_social_login:
                # For social login, we need to complete the social auth process
                from allauth.socialaccount.models import SocialAccount
                
                # Check if user already has social account
                social_account = SocialAccount.objects.filter(user=self.user, provider=self.social_provider).first()
                
                if social_account:
                    # Login the user directly
                    login(self.request, self.user)
                    # Record the login
                    self.user.record_login(self.request)
                else:
                    # This shouldn't happen, but handle gracefully
                    login(self.request, self.user)
            else:
                # Normal login
                login(self.request, self.user)
                self.user.record_login(self.request)
            
            # Clear 2FA session data
            session_keys = ['2fa_user_id', '2fa_next_url', '2fa_social_login', '2fa_social_provider']
            for key in session_keys:
                if key in self.request.session:
                    del self.request.session[key]
            
            messages.success(self.request, f'Welcome back, {self.user.get_full_name()}!')
            
            # Redirect to next URL
            return redirect(self.get_success_url())
        else:
            messages.error(self.request, 'Invalid verification code. Please try again.')
            return self.form_invalid(form)
                
class TwoFactorDisableView(LoginRequiredMixin, FormView):
    """
    View for disabling 2FA.
    """
    template_name = 'accounts/2fa_disable.html'
    form_class = TwoFactorVerifyForm
    success_url = reverse_lazy('accounts:security_settings')

    def form_valid(self, form):
        code = form.cleaned_data['code']
        security = self.request.user.security_settings
        
        if security.verify_2fa_code(code):
            security.two_factor_enabled = False
            security.two_factor_secret = ''
            security.two_factor_backup_codes = []
            security.save()
            
            messages.success(self.request, 'Two-factor authentication disabled successfully.')
            return super().form_valid(form)
        else:
            messages.error(self.request, 'Invalid verification code.')
            return self.form_invalid(form)


# ===== PASSWORD RESET VIEWS (API Compatible) =====

class PasswordResetView(FormView):
    """
    API-compatible password reset request view.
    This handles both web forms and can be adapted for API responses.
    """
    template_name = 'accounts/password_reset.html'
    form_class = PasswordResetRequestForm
    success_url = reverse_lazy('accounts:password_reset_done')

    def form_valid(self, form):
        email = form.cleaned_data['email']
        
        try:
            user = User.objects.get(email=email)
            
            # Generate reset token
            token = secrets.token_urlsafe(32)
            PasswordReset.objects.create(
                user=user,
                token=token,
                expires_at=timezone.now() + timezone.timedelta(hours=1),
                ip_address=self.request.META.get('REMOTE_ADDR', ''),
                user_agent=self.request.META.get('HTTP_USER_AGENT', '')
            )
            
            # Send reset email
            reset_url = f"{settings.SITE_URL}/auth/password-reset/{token}/"
            
            html_message = render_to_string('accounts/emails/password_reset.html', {
                'user': user,
                'reset_url': reset_url
            })
            
            send_mail(
                'Password Reset Request - FlynJet',
                f'Click here to reset your password: {reset_url}',
                settings.DEFAULT_FROM_EMAIL,
                [email],
                html_message=html_message,
                fail_silently=False,
            )
            
            # For API responses, you might want to return JSON instead
            if self.request.headers.get('accept') == 'application/json':
                from django.http import JsonResponse
                return JsonResponse({
                    'status': 'success',
                    'message': 'Password reset email sent if the email exists.'
                })
            
        except User.DoesNotExist:
            # Don't reveal that user doesn't exist
            pass
        
        return super().form_valid(form)


# ===== ADD THESE TO YOUR URLS.PY IMPORTS =====
# Make sure these classes are available for import
__all__ = [
    'RegisterView',
    'LoginView',
    'LogoutView',
    'VerifyEmailView',
    'ResendVerificationView',
    'ProfileView',
    'EditProfileView',
    'SecuritySettingsView',
    'TwoFactorSetupView',
    'TwoFactorAuthView',
    'TwoFactorDisableView',
    'PasswordResetView',  # If you added the alias
    'PasswordResetRequestView',
    'PasswordResetDoneView',
    'PasswordResetConfirmView',
    'PasswordResetCompleteView',
    'PasswordChangeView',
]