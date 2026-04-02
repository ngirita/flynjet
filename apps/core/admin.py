from django.contrib import admin
from django.utils import timezone
from .models import (
    SiteSettings, Notification, SupportTicket, SupportMessage, 
    FAQ, Testimonial, ActivityLog, AdminNotification,  # Add AdminNotification here
    BankDetail, CryptoWallet, OfficeLocation, CompanyContact, PaymentMethodConfig
)
from .models import SocialLink

@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    list_display = ['company_name', 'company_email', 'company_phone', 'updated_at']
    
    def has_add_permission(self, request):
        # Only allow one settings object
        return not SiteSettings.objects.exists()
    
    def has_delete_permission(self, request, obj=None):
        # Prevent deletion
        return False

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['title', 'recipient', 'notification_type', 'priority', 'is_read', 'created_at']
    list_filter = ['notification_type', 'priority', 'is_read', 'created_at']
    search_fields = ['title', 'message', 'recipient__email']
    date_hierarchy = 'created_at'
    actions = ['mark_as_read']
    
    def mark_as_read(self, request, queryset):
        queryset.update(is_read=True)
    mark_as_read.short_description = "Mark selected as read"

@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ['ticket_number', 'user', 'subject', 'category', 'status', 'priority', 'created_at']
    list_filter = ['status', 'priority', 'category', 'created_at']
    search_fields = ['ticket_number', 'user__email', 'subject']
    readonly_fields = ['ticket_number', 'created_at', 'updated_at']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Ticket Information', {
            'fields': ('ticket_number', 'user', 'booking', 'category', 'status', 'priority')
        }),
        ('Content', {
            'fields': ('subject', 'description')
        }),
        ('Assignment', {
            'fields': ('assigned_to', 'assigned_at')
        }),
        ('Resolution', {
            'fields': ('resolution', 'resolved_at', 'resolved_by')
        }),
        ('Feedback', {
            'fields': ('rating', 'feedback')
        }),
        ('Metadata', {
            'fields': ('ip_address', 'user_agent', 'attachments'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['assign_to_me', 'mark_resolved', 'escalate']
    
    def assign_to_me(self, request, queryset):
        queryset.update(assigned_to=request.user, assigned_at=timezone.now(), status='open')
    assign_to_me.short_description = "Assign to me"
    
    def mark_resolved(self, request, queryset):
        queryset.update(status='resolved', resolved_at=timezone.now(), resolved_by=request.user)
    mark_resolved.short_description = "Mark as resolved"
    
    def escalate(self, request, queryset):
        queryset.update(priority='urgent', status='escalated')
    escalate.short_description = "Escalate tickets"

@admin.register(SupportMessage)
class SupportMessageAdmin(admin.ModelAdmin):
    list_display = ['ticket', 'sender', 'created_at', 'is_read', 'is_internal']
    list_filter = ['is_read', 'is_internal', 'created_at']
    search_fields = ['ticket__ticket_number', 'message']

@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ['question', 'category', 'sort_order', 'is_published', 'views_count']
    list_filter = ['category', 'is_published']
    search_fields = ['question', 'answer']
    list_editable = ['sort_order', 'is_published']
    
    fieldsets = (
        (None, {
            'fields': ('question', 'answer', 'category', 'sort_order', 'is_published')
        }),
        ('SEO', {
            'fields': ('meta_title', 'meta_description'),
            'classes': ('collapse',)
        }),
        ('Statistics', {
            'fields': ('views_count', 'helpful_count', 'not_helpful_count'),
            'classes': ('collapse',)
        }),
    )

@admin.register(Testimonial)
class TestimonialAdmin(admin.ModelAdmin):
    list_display = ['customer_name', 'rating', 'is_featured', 'is_verified', 'is_published', 'created_at']
    list_filter = ['rating', 'is_featured', 'is_verified', 'is_published']
    search_fields = ['customer_name', 'content']
    list_editable = ['is_featured', 'is_published']
    
    actions = ['verify_testimonials']
    
    def verify_testimonials(self, request, queryset):
        for testimonial in queryset:
            testimonial.verify(request.user)
    verify_testimonials.short_description = "Verify selected testimonials"

@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ['user', 'activity_type', 'description', 'timestamp']
    list_filter = ['activity_type', 'timestamp']
    search_fields = ['user__email', 'description']
    readonly_fields = ['user', 'activity_type', 'description', 'ip_address', 'user_agent', 'timestamp', 'data']
    date_hierarchy = 'timestamp'
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False
    
@admin.register(AdminNotification)
class AdminNotificationAdmin(admin.ModelAdmin):
    list_display = ['notification_type', 'title', 'is_read', 'created_at']
    list_filter = ['notification_type', 'is_read', 'created_at']
    search_fields = ['title', 'message']
    readonly_fields = ['notification_type', 'title', 'message', 'link', 'created_at']
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False

# apps/core/admin.py - Add these registrations


@admin.register(BankDetail)
class BankDetailAdmin(admin.ModelAdmin):
    list_display = ['bank_name', 'account_name', 'account_number', 'currency', 'is_active', 'is_default']
    list_filter = ['is_active', 'is_default', 'currency', 'country']
    search_fields = ['bank_name', 'account_name', 'account_number']
    list_editable = ['is_active']
    
    fieldsets = (
        ('Bank Information', {
            'fields': ('bank_name', 'account_name', 'account_number', 'currency', 'country')
        }),
        ('Routing Information', {
            'fields': ('routing_number', 'swift_code', 'iban')
        }),
        ('Address', {
            'fields': ('branch_address',)
        }),
        ('Settings', {
            'fields': ('is_active', 'is_default', 'sort_order')
        }),
        ('Notes', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['make_default', 'activate_selected', 'deactivate_selected']
    
    def make_default(self, request, queryset):
        queryset.update(is_default=True)
        self.message_user(request, f"{queryset.count()} bank details set as default.")
    make_default.short_description = "Set as default"
    
    def activate_selected(self, request, queryset):
        queryset.update(is_active=True)
        self.message_user(request, f"{queryset.count()} bank details activated.")
    activate_selected.short_description = "Activate selected"
    
    def deactivate_selected(self, request, queryset):
        queryset.update(is_active=False)
        self.message_user(request, f"{queryset.count()} bank details deactivated.")
    deactivate_selected.short_description = "Deactivate selected"


@admin.register(CryptoWallet)
class CryptoWalletAdmin(admin.ModelAdmin):
    list_display = ['crypto_type', 'network', 'short_address', 'is_active', 'is_default', 'has_link']
    list_filter = ['crypto_type', 'network', 'is_active']
    search_fields = ['wallet_address', 'wallet_name']
    list_editable = ['is_active']
    
    def short_address(self, obj):
        return obj.wallet_address[:25] + '...' if len(obj.wallet_address) > 25 else obj.wallet_address
    short_address.short_description = "Wallet Address"
    
    def has_link(self, obj):
        return "🔗" if obj.link_url else "—"
    has_link.short_description = "Link"
    
    fieldsets = (
        ('Wallet Information', {
            'fields': ('crypto_type', 'network', 'wallet_address', 'wallet_name')
        }),
        ('Optional Link', {
            'fields': ('link_url', 'link_text'),
            'classes': ('collapse',),
            'description': 'Add an optional link (e.g., blockchain explorer, exchange link)'
        }),
        ('Limits', {
            'fields': ('min_deposit', 'max_deposit')
        }),
        ('Settings', {
            'fields': ('is_active', 'is_default', 'sort_order')
        }),
        ('QR Code', {
            'fields': ('qr_code',),
            'classes': ('collapse',)
        }),
        ('Notes', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['make_default', 'activate_selected', 'deactivate_selected']
    
    def make_default(self, request, queryset):
        for wallet in queryset:
            wallet.is_default = True
            wallet.save()
        self.message_user(request, f"{queryset.count()} wallets set as default.")
    make_default.short_description = "Set as default"
    
    def activate_selected(self, request, queryset):
        queryset.update(is_active=True)
        self.message_user(request, f"{queryset.count()} wallets activated.")
    activate_selected.short_description = "Activate selected"
    
    def deactivate_selected(self, request, queryset):
        queryset.update(is_active=False)
        self.message_user(request, f"{queryset.count()} wallets deactivated.")
    deactivate_selected.short_description = "Deactivate selected"

@admin.register(OfficeLocation)
class OfficeLocationAdmin(admin.ModelAdmin):
    list_display = ['city', 'country', 'short_address', 'phone', 'is_active', 'is_headquarters']
    list_filter = ['country', 'is_active']
    search_fields = ['city', 'country', 'address']
    list_editable = ['is_active']
    
    def short_address(self, obj):
        return obj.address[:40] + '...' if len(obj.address) > 40 else obj.address
    short_address.short_description = "Address"
    
    fieldsets = (
        ('Location', {
            'fields': ('city', 'country', 'address', 'working_hours')
        }),
        ('Contact', {
            'fields': ('phone', 'email')
        }),
        ('Map Coordinates', {
            'fields': ('latitude', 'longitude'),
            'classes': ('collapse',)
        }),
        ('Settings', {
            'fields': ('is_active', 'is_headquarters', 'sort_order')
        }),
    )
    
    actions = ['activate_selected', 'deactivate_selected', 'set_as_headquarters']
    
    def set_as_headquarters(self, request, queryset):
        queryset.update(is_headquarters=True)
        self.message_user(request, f"{queryset.count()} offices set as headquarters.")
    set_as_headquarters.short_description = "Set as headquarters"
    
    def activate_selected(self, request, queryset):
        queryset.update(is_active=True)
        self.message_user(request, f"{queryset.count()} offices activated.")
    activate_selected.short_description = "Activate selected"
    
    def deactivate_selected(self, request, queryset):
        queryset.update(is_active=False)
        self.message_user(request, f"{queryset.count()} offices deactivated.")
    deactivate_selected.short_description = "Deactivate selected"


@admin.register(CompanyContact)
class CompanyContactAdmin(admin.ModelAdmin):
    list_display = ['contact_type', 'value', 'label', 'is_active', 'is_primary']
    list_filter = ['contact_type', 'is_active']
    search_fields = ['value', 'label']
    list_editable = ['is_active']
    
    fieldsets = (
        (None, {
            'fields': ('contact_type', 'value', 'label')
        }),
        ('Settings', {
            'fields': ('is_active', 'is_primary', 'sort_order')
        }),
    )
    
    actions = ['make_primary', 'activate_selected', 'deactivate_selected']
    
    def make_primary(self, request, queryset):
        for contact in queryset:
            contact.is_primary = True
            contact.save()
        self.message_user(request, f"{queryset.count()} contacts set as primary.")
    make_primary.short_description = "Set as primary"
    
    def activate_selected(self, request, queryset):
        queryset.update(is_active=True)
        self.message_user(request, f"{queryset.count()} contacts activated.")
    activate_selected.short_description = "Activate selected"
    
    def deactivate_selected(self, request, queryset):
        queryset.update(is_active=False)
        self.message_user(request, f"{queryset.count()} contacts deactivated.")
    deactivate_selected.short_description = "Deactivate selected"


@admin.register(PaymentMethodConfig)
class PaymentMethodConfigAdmin(admin.ModelAdmin):
    list_display = ['display_name', 'method_key', 'get_status_display', 'is_visible', 'sort_order']
    list_filter = ['is_enabled', 'is_visible', 'is_maintenance']
    search_fields = ['display_name', 'method_key']
    list_editable = ['sort_order']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('method_key', 'display_name', 'description', 'icon_class')
        }),
        ('Status', {
            'fields': ('is_enabled', 'is_visible', 'is_maintenance', 'maintenance_message')
        }),
        ('Fees', {
            'fields': ('fee_percentage', 'fee_fixed')
        }),
        ('Limits', {
            'fields': ('min_amount', 'max_amount')
        }),
        ('Display', {
            'fields': ('sort_order',)
        }),
    )
    
    actions = ['enable_selected', 'disable_selected', 'maintenance_on', 'maintenance_off']
    
    def get_status_display(self, obj):
        if not obj.is_enabled:
            return '🔴 Disabled'
        if obj.is_maintenance:
            return '🟡 Maintenance'
        return '🟢 Active'
    get_status_display.short_description = "Status"
    
    def enable_selected(self, request, queryset):
        queryset.update(is_enabled=True, is_maintenance=False)
        self.message_user(request, f"{queryset.count()} payment methods enabled.")
    enable_selected.short_description = "Enable selected"
    
    def disable_selected(self, request, queryset):
        queryset.update(is_enabled=False, is_maintenance=False)
        self.message_user(request, f"{queryset.count()} payment methods disabled.")
    disable_selected.short_description = "Disable selected"
    
    def maintenance_on(self, request, queryset):
        queryset.update(is_maintenance=True, is_enabled=True)
        self.message_user(request, f"{queryset.count()} payment methods put into maintenance mode.")
    maintenance_on.short_description = "Maintenance mode ON"
    
    def maintenance_off(self, request, queryset):
        queryset.update(is_maintenance=False)
        self.message_user(request, f"{queryset.count()} payment methods taken out of maintenance mode.")
    maintenance_off.short_description = "Maintenance mode OFF"


@admin.register(SocialLink)
class SocialLinkAdmin(admin.ModelAdmin):
    list_display = ['platform', 'get_display_name', 'short_url', 'is_active', 'sort_order']
    list_filter = ['platform', 'is_active']
    search_fields = ['url', 'custom_name']
    list_editable = ['is_active', 'sort_order']
    
    def short_url(self, obj):
        return obj.url[:50] + '...' if len(obj.url) > 50 else obj.url
    short_url.short_description = "URL"
    
    fieldsets = (
        ('Social Media Information', {
            'fields': ('platform', 'url', 'custom_name')
        }),
        ('Display Settings', {
            'fields': ('icon_class', 'is_active', 'open_in_new_tab', 'sort_order')
        }),
        ('Tracking (Optional)', {
            'fields': ('utm_source', 'utm_medium', 'utm_campaign'),
            'classes': ('collapse',),
        }),
    )
    
    actions = ['activate_selected', 'deactivate_selected']
    
    def activate_selected(self, request, queryset):
        queryset.update(is_active=True)
        self.message_user(request, f"{queryset.count()} social links activated.")
    activate_selected.short_description = "Activate selected"
    
    def deactivate_selected(self, request, queryset):
        queryset.update(is_active=False)
        self.message_user(request, f"{queryset.count()} social links deactivated.")
    deactivate_selected.short_description = "Deactivate selected"