from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from .models import (
    User, UserProfile, LoginHistory, UserSecuritySettings,
    UserNotificationPreferences, EmailVerification, PasswordReset,
    UserDevice, AuditLog
)
from apps.core.models import Notification # Import Notification from core

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = [
        'email', 'get_full_name', 'user_type', 'is_active', 
        'is_suspended', 'email_verified', 'date_joined', 'last_login'
    ]
    list_filter = ['user_type', 'is_active', 'is_suspended', 'email_verified', 'date_joined']
    search_fields = ['email', 'first_name', 'last_name', 'phone_number']
    readonly_fields = ['date_joined', 'last_login', 'last_login_ip', 'profile_link', 'security_link']
    
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {
            'fields': (
                'first_name', 'last_name', 'username', 'phone_number',
                'alternate_phone', 'date_of_birth'
            )
        }),
        ('Address', {
            'fields': (
                'address_line1', 'address_line2', 'city', 'state',
                'country', 'postal_code'
            )
        }),
        ('Company Info', {
            'fields': (
                'company_name', 'company_registration_number',
                'company_vat_number', 'company_website'
            )
        }),
        ('Verification', {
            'fields': (
                'email_verified', 'phone_verified', 'identity_verified',
                'verified_at', 'id_verification_status'
            )
        }),
        ('Document Verification', {
            'fields': (
                'id_document_type', 'id_document_number',
                'id_document_front', 'id_document_back'
            )
        }),
        ('Preferences', {
            'fields': ('preferred_language', 'preferred_currency')
        }),
        ('Permissions', {
            'fields': (
                'user_type', 'is_active', 'is_staff', 'is_superuser',
                'is_suspended', 'suspension_reason', 'suspended_until',
                'groups', 'user_permissions'
            )
        }),
        ('Security', {
            'fields': (
                'last_login_ip', 'last_login_user_agent',
                'failed_login_attempts', 'last_failed_login',
                'account_locked_until'
            )
        }),
        ('Important dates', {
            'fields': (
                'date_joined', 'last_login', 'last_activity',
                'deactivated_at'
            )
        }),
        ('Metadata', {'fields': ('metadata',)}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'email', 'first_name', 'last_name', 'phone_number',
                'password1', 'password2', 'user_type'
            ),
        }),
    )
    
    actions = ['suspend_users', 'activate_users', 'verify_emails', 'send_welcome_email']
    
    def get_full_name(self, obj):
        return obj.get_full_name()
    get_full_name.short_description = 'Full Name'
    get_full_name.admin_order_field = 'first_name'
    
    def profile_link(self, obj):
        url = reverse('admin:accounts_userprofile_change', args=[obj.profile.id])
        return format_html('<a href="{}">View Profile</a>', url)
    profile_link.short_description = 'Profile'
    
    def security_link(self, obj):
        url = reverse('admin:accounts_usersecuritysettings_change', args=[obj.security_settings.id])
        return format_html('<a href="{}">Security Settings</a>', url)
    security_link.short_description = 'Security'
    
    def suspend_users(self, request, queryset):
        for user in queryset:
            user.suspend_account('Suspended by admin')
        self.message_user(request, f"{queryset.count()} users suspended.")
    suspend_users.short_description = "Suspend selected users"
    
    def activate_users(self, request, queryset):
        for user in queryset:
            user.reactivate_account()
        self.message_user(request, f"{queryset.count()} users activated.")
    activate_users.short_description = "Activate selected users"
    
    def verify_emails(self, request, queryset):
        queryset.update(email_verified=True, verified_at=timezone.now())
        self.message_user(request, f"{queryset.count()} users email verified.")
    verify_emails.short_description = "Verify email for selected users"
    
    def send_welcome_email(self, request, queryset):
        for user in queryset:
            user.email_user(
                'Welcome to FlynJet',
                'Thank you for joining FlynJet. We look forward to serving you!'
            )
        self.message_user(request, f"Welcome emails sent to {queryset.count()} users.")
    send_welcome_email.short_description = "Send welcome email"


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'nationality', 'passport_number', 'emergency_contact_name']
    search_fields = ['user__email', 'user__first_name', 'user__last_name', 'passport_number']
    readonly_fields = ['profile_image_preview']
    
    fieldsets = (
        ('User', {'fields': ('user',)}),
        ('Profile Image', {'fields': ('profile_image', 'profile_image_preview')}),
        ('Personal Details', {
            'fields': (
                'gender', 'nationality', 'passport_number', 'passport_expiry',
                'frequent_flyer_number', 'preferred_airport'
            )
        }),
        ('Emergency Contact', {
            'fields': (
                'emergency_contact_name', 'emergency_contact_phone',
                'emergency_contact_relation'
            )
        }),
        ('Special Requirements', {
            'fields': (
                'dietary_restrictions', 'medical_conditions',
                'special_assistance_required'
            )
        }),
        ('Travel Preferences', {
            'fields': ('seat_preference', 'meal_preference')
        }),
        ('Corporate', {
            'fields': (
                'corporate_title', 'corporate_department', 'corporate_cost_center'
            )
        }),
    )
    
    def profile_image_preview(self, obj):
        if obj.profile_image:
            return format_html(
                '<img src="{}" style="max-height: 200px; max-width: 200px;" />',
                obj.profile_image.url
            )
        return "No image"
    profile_image_preview.short_description = "Preview"


@admin.register(LoginHistory)
class LoginHistoryAdmin(admin.ModelAdmin):
    list_display = ['user', 'login_type', 'ip_address', 'success', 'timestamp']
    list_filter = ['login_type', 'success', 'timestamp']
    search_fields = ['user__email', 'ip_address']
    readonly_fields = ['timestamp']
    date_hierarchy = 'timestamp'


@admin.register(UserSecuritySettings)
class UserSecuritySettingsAdmin(admin.ModelAdmin):
    list_display = ['user', 'two_factor_enabled', 'session_timeout', 'api_key_created']
    list_filter = ['two_factor_enabled']
    search_fields = ['user__email']
    readonly_fields = ['api_key', 'api_key_created', 'api_key_last_used']
    
    fieldsets = (
        ('User', {'fields': ('user',)}),
        ('Two Factor Authentication', {
            'fields': (
                'two_factor_enabled', 'two_factor_secret',
                'two_factor_backup_codes', 'two_factor_last_used'
            )
        }),
        ('Session Management', {
            'fields': ('session_timeout', 'max_concurrent_sessions', 'remember_device_days')
        }),
        ('Login Alerts', {
            'fields': (
                'alert_on_new_device', 'alert_on_new_location',
                'alert_on_failed_login', 'alert_email', 'alert_sms'
            )
        }),
        ('Password Policy', {
            'fields': ('password_last_changed', 'password_expiry_days', 'password_history')
        }),
        ('API Security', {
            'fields': ('api_key', 'api_key_created', 'api_key_last_used', 'api_rate_limit')
        }),
        ('Trusted Devices', {'fields': ('trusted_devices',)}),
    )

