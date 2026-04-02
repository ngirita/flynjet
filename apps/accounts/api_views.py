from rest_framework import viewsets, status, generics, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView
from django.contrib.auth import get_user_model, authenticate, login, logout
from django.utils import timezone
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
import secrets
from .models import User, UserProfile, LoginHistory, UserSecuritySettings
from .serializers import (
    UserSerializer, UserProfileSerializer, LoginHistorySerializer,
    RegisterSerializer, LoginSerializer, UserSecuritySerializer,
    PasswordChangeSerializer, PasswordResetSerializer, PasswordResetConfirmSerializer
)
from .permissions import IsOwnerOrReadOnly, IsAdminOrAgent
from .utils import generate_verification_token, send_verification_email

User = get_user_model()

class UserViewSet(viewsets.ModelViewSet):
    """
    ViewSet for User operations.
    """
    queryset = User.objects.all().order_by('-date_joined')
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrReadOnly]
    
    def get_queryset(self):
        """Filter queryset based on user permissions."""
        user = self.request.user
        
        # Admin can see all users
        if user.is_staff or user.user_type == 'admin':
            return User.objects.all()
        
        # Regular users can only see themselves
        return User.objects.filter(id=user.id)
    
    @action(detail=False, methods=['get'])
    def me(self, request):
        """Get current user profile."""
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)
    
    @action(detail=False, methods=['put', 'patch'])
    def update_profile(self, request):
        """Update current user profile."""
        user = request.user
        serializer = self.get_serializer(user, data=request.data, partial=True)
        
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'])
    def change_password(self, request):
        """Change user password."""
        serializer = PasswordChangeSerializer(data=request.data, context={'request': request})
        
        if serializer.is_valid():
            user = request.user
            user.set_password(serializer.validated_data['new_password'])
            user.save()
            
            # Update security settings
            security = user.security_settings
            security.password_changed_at = timezone.now()
            security.add_to_password_history(user.password)
            security.save()
            
            return Response({'message': 'Password changed successfully'})
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'])
    def verify_email(self, request):
        """Verify email with token."""
        token = request.data.get('token')
        
        from .models import EmailVerification
        try:
            verification = EmailVerification.objects.get(token=token)
            if verification.is_valid():
                verification.verify()
                return Response({'message': 'Email verified successfully'})
            else:
                return Response(
                    {'error': 'Verification link expired'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except EmailVerification.DoesNotExist:
            return Response(
                {'error': 'Invalid verification token'},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['post'])
    def resend_verification(self, request):
        """Resend verification email."""
        user = request.user
        
        if user.email_verified:
            return Response(
                {'error': 'Email already verified'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        send_verification_email(user, request)
        return Response({'message': 'Verification email sent'})


class LoginHistoryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing login history.
    """
    serializer_class = LoginHistorySerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Return login history for current user."""
        return LoginHistory.objects.filter(user=self.request.user).order_by('-timestamp')


class RegisterView(generics.CreateAPIView):
    """
    API endpoint for user registration.
    """
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]
    
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        
        if serializer.is_valid():
            user = serializer.save()
            
            # Send verification email
            send_verification_email(user, request)
            
            # Return user data
            user_data = UserSerializer(user, context={'request': request}).data
            return Response({
                'user': user_data,
                'message': 'Registration successful. Please check your email to verify your account.'
            }, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LoginView(generics.GenericAPIView):
    """
    API endpoint for user login.
    """
    serializer_class = LoginSerializer
    permission_classes = [permissions.AllowAny]
    
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        
        if serializer.is_valid():
            email = serializer.validated_data['email']
            password = serializer.validated_data['password']
            
            user = authenticate(request, email=email, password=password)
            
            if user is not None:
                if user.is_account_locked():
                    return Response(
                        {'error': 'Account is locked. Please try again later.'},
                        status=status.HTTP_403_FORBIDDEN
                    )
                
                # Check 2FA
                if user.security_settings.two_factor_enabled:
                    # Return 2FA required status
                    return Response({
                        'requires_2fa': True,
                        'user_id': user.id
                    }, status=status.HTTP_200_OK)
                
                # Login user
                login(request, user)
                user.record_login(request)
                
                # Get tokens
                from rest_framework_simplejwt.tokens import RefreshToken
                refresh = RefreshToken.for_user(user)
                
                return Response({
                    'user': UserSerializer(user, context={'request': request}).data,
                    'access': str(refresh.access_token),
                    'refresh': str(refresh),
                    'message': 'Login successful'
                })
            else:
                # Record failed login attempt
                try:
                    user = User.objects.get(email=email)
                    user.record_failed_login()
                except User.DoesNotExist:
                    pass
                
                return Response(
                    {'error': 'Invalid email or password'},
                    status=status.HTTP_401_UNAUTHORIZED
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LogoutView(generics.GenericAPIView):
    """
    API endpoint for user logout.
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        # Record logout
        LoginHistory.objects.create(
            user=request.user,
            ip_address=request.user.get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            login_type='logout'
        )
        
        logout(request)
        return Response({'message': 'Logout successful'})


class TwoFactorAuthView(generics.GenericAPIView):
    """
    API endpoint for 2FA verification.
    """
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        user_id = request.data.get('user_id')
        code = request.data.get('code')
        
        try:
            user = User.objects.get(id=user_id)
            
            if user.security_settings.verify_2fa_code(code):
                # Login user after 2FA verification
                login(request, user)
                user.record_login(request)
                
                # Get tokens
                from rest_framework_simplejwt.tokens import RefreshToken
                refresh = RefreshToken.for_user(user)
                
                return Response({
                    'user': UserSerializer(user, context={'request': request}).data,
                    'access': str(refresh.access_token),
                    'refresh': str(refresh),
                    'message': '2FA verification successful'
                })
            else:
                return Response(
                    {'error': 'Invalid 2FA code'},
                    status=status.HTTP_401_UNAUTHORIZED
                )
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found'},
                status=status.HTTP_404_NOT_FOUND
            )


class TwoFactorSetupView(generics.GenericAPIView):
    """
    API endpoint for setting up 2FA.
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        """Get 2FA setup information."""
        security = request.user.security_settings
        
        if security.two_factor_enabled:
            return Response({
                'enabled': True,
                'message': '2FA is already enabled'
            })
        
        # Generate QR code
        qr_code = security.generate_2fa_qr_code()
        backup_codes = security.generate_backup_codes()
        
        return Response({
            'enabled': False,
            'qr_code': qr_code,
            'backup_codes': backup_codes,
            'secret': security.two_factor_secret
        })
    
    def post(self, request):
        """Enable 2FA after verification."""
        code = request.data.get('code')
        security = request.user.security_settings
        
        if security.verify_2fa_code(code):
            security.two_factor_enabled = True
            security.save()
            return Response({'message': '2FA enabled successfully'})
        else:
            return Response(
                {'error': 'Invalid verification code'},
                status=status.HTTP_400_BAD_REQUEST
            )


class TwoFactorDisableView(generics.GenericAPIView):
    """
    API endpoint for disabling 2FA.
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        """Disable 2FA."""
        password = request.data.get('password')
        
        # Verify password
        if not request.user.check_password(password):
            return Response(
                {'error': 'Invalid password'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        security = request.user.security_settings
        security.two_factor_enabled = False
        security.two_factor_secret = ''
        security.two_factor_backup_codes = []
        security.save()
        
        return Response({'message': '2FA disabled successfully'})


class PasswordResetView(generics.GenericAPIView):
    """
    API endpoint for requesting password reset.
    """
    serializer_class = PasswordResetSerializer
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        
        if serializer.is_valid():
            email = serializer.validated_data['email']
            
            try:
                user = User.objects.get(email=email)
                
                # Generate reset token
                from .models import PasswordReset
                token = secrets.token_urlsafe(32)
                
                PasswordReset.objects.create(
                    user=user,
                    token=token,
                    expires_at=timezone.now() + timezone.timedelta(hours=1),
                    ip_address=request.META.get('REMOTE_ADDR', ''),
                    user_agent=request.META.get('HTTP_USER_AGENT', '')
                )
                
                # Send reset email
                reset_url = f"{settings.SITE_URL}/reset-password/{token}/"
                
                send_mail(
                    'Password Reset Request',
                    f'Click here to reset your password: {reset_url}',
                    settings.DEFAULT_FROM_EMAIL,
                    [email],
                    fail_silently=False,
                )
                
            except User.DoesNotExist:
                # Don't reveal that user doesn't exist
                pass
            
            return Response({'message': 'If the email exists, a reset link has been sent'})
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PasswordResetConfirmView(generics.GenericAPIView):
    """
    API endpoint for confirming password reset.
    """
    serializer_class = PasswordResetConfirmSerializer
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        
        if serializer.is_valid():
            token = serializer.validated_data['token']
            password = serializer.validated_data['new_password']
            
            from .models import PasswordReset
            try:
                reset = PasswordReset.objects.get(token=token)
                
                if reset.is_valid():
                    # Reset password
                    user = reset.user
                    user.set_password(password)
                    user.save()
                    
                    # Mark token as used
                    reset.mark_used()
                    
                    # Update security settings
                    security = user.security_settings
                    security.password_changed_at = timezone.now()
                    security.add_to_password_history(user.password)
                    security.save()
                    
                    return Response({'message': 'Password reset successful'})
                else:
                    return Response(
                        {'error': 'Reset link expired'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                    
            except PasswordReset.DoesNotExist:
                return Response(
                    {'error': 'Invalid reset token'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ProfileView(generics.RetrieveUpdateAPIView):
    """
    API endpoint for user profile.
    """
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_object(self):
        return self.request.user.profile


class SecuritySettingsView(generics.RetrieveUpdateAPIView):
    """
    API endpoint for user security settings.
    """
    serializer_class = UserSecuritySerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_object(self):
        return self.request.user.security_settings


class VerifyEmailView(generics.GenericAPIView):
    """
    API endpoint for email verification.
    """
    permission_classes = [permissions.AllowAny]
    
    def get(self, request, token):
        from .models import EmailVerification
        try:
            verification = EmailVerification.objects.get(token=token)
            if verification.is_valid():
                verification.verify()
                return Response({'message': 'Email verified successfully'})
            else:
                return Response(
                    {'error': 'Verification link expired'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except EmailVerification.DoesNotExist:
            return Response(
                {'error': 'Invalid verification token'},
                status=status.HTTP_404_NOT_FOUND
            )


class UserActivityView(generics.GenericAPIView):
    """
    API endpoint for user activity.
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        user = request.user
        
        # Get recent login history
        recent_logins = LoginHistory.objects.filter(user=user)[:10]
        
        # Get recent bookings
        recent_bookings = user.bookings.all()[:5]
        
        from apps.bookings.serializers import BookingSerializer
        
        return Response({
            'last_login': user.last_login,
            'last_activity': user.last_activity,
            'recent_logins': LoginHistorySerializer(recent_logins, many=True).data,
            'recent_bookings': BookingSerializer(recent_bookings, many=True).data,
            'total_bookings': user.bookings.count(),
            'account_age_days': (timezone.now() - user.date_joined).days
        })