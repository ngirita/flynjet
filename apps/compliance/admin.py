from django.contrib import admin
from .models import ConsentRecord, DataProcessingAgreement, DataSubjectRequest, BreachNotification

@admin.register(ConsentRecord)
class ConsentRecordAdmin(admin.ModelAdmin):
    list_display = ['user', 'consent_type', 'version', 'granted', 'created_at', 'withdrawn_at']
    list_filter = ['consent_type', 'granted', 'created_at']
    search_fields = ['user__email', 'user__first_name', 'user__last_name']
    readonly_fields = ['created_at', 'withdrawn_at', 'ip_address', 'user_agent']
    
    fieldsets = (
        ('Consent Info', {
            'fields': ('user', 'consent_type', 'version', 'granted')
        }),
        ('Documentation', {
            'fields': ('document_url',)
        }),
        ('Withdrawal', {
            'fields': ('withdrawn_at', 'withdrawal_ip')
        }),
        ('Metadata', {
            'fields': ('ip_address', 'user_agent', 'created_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['withdraw_consent']
    
    def withdraw_consent(self, request, queryset):
        for consent in queryset:
            consent.withdraw(request.META.get('REMOTE_ADDR'))
        self.message_user(request, f"{queryset.count()} consents withdrawn.")
    withdraw_consent.short_description = "Withdraw selected consents"

@admin.register(DataProcessingAgreement)
class DataProcessingAgreementAdmin(admin.ModelAdmin):
    list_display = ['company_name', 'agreement_number', 'agreement_type', 'effective_date', 'expiry_date', 'is_active']
    list_filter = ['agreement_type', 'is_active', 'effective_date']
    search_fields = ['company_name', 'agreement_number', 'contact_email']
    readonly_fields = ['agreement_number', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Agreement Info', {
            'fields': ('agreement_number', 'company_name', 'agreement_type', 'is_active')
        }),
        ('Contact Details', {
            'fields': ('contact_name', 'contact_email', 'contact_phone')
        }),
        ('Dates', {
            'fields': ('signed_date', 'effective_date', 'expiry_date')
        }),
        ('Purpose & Data', {
            'fields': ('purpose', 'data_categories')
        }),
        ('Security', {
            'fields': ('security_measures', 'breach_notification_time')
        }),
        ('Document', {
            'fields': ('agreement_file',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['mark_inactive', 'send_reminder']
    
    def mark_inactive(self, request, queryset):
        queryset.update(is_active=False)
        self.message_user(request, f"{queryset.count()} agreements marked inactive.")
    mark_inactive.short_description = "Mark as inactive"
    
    def send_reminder(self, request, queryset):
        for agreement in queryset:
            if agreement.is_expiring_soon():
                # Send reminder email
                from django.core.mail import send_mail
                send_mail(
                    f"DPA Expiring Soon - {agreement.company_name}",
                    f"Your data processing agreement with {agreement.company_name} expires on {agreement.expiry_date}.",
                    'info@flynjet.com',
                    [agreement.contact_email],
                    fail_silently=False,
                )
        self.message_user(request, f"Reminders sent for {queryset.count()} agreements.")
    send_reminder.short_description = "Send expiry reminders"

@admin.register(DataSubjectRequest)
class DataSubjectRequestAdmin(admin.ModelAdmin):
    list_display = ['request_number', 'requester_name', 'requester_email', 'request_type', 'status', 'submitted_at', 'deadline']
    list_filter = ['request_type', 'status', 'submitted_at']
    search_fields = ['request_number', 'requester_email', 'requester_name']
    readonly_fields = ['request_number', 'submitted_at', 'deadline']
    
    fieldsets = (
        ('Request Info', {
            'fields': ('request_number', 'request_type', 'status')
        }),
        ('Requester', {
            'fields': ('requester_name', 'requester_email', 'user')
        }),
        ('Description', {
            'fields': ('description',)
        }),
        ('Timeline', {
            'fields': ('submitted_at', 'deadline', 'completed_at', 'verified_at')
        }),
        ('Response', {
            'fields': ('response_file', 'response_notes')
        }),
        ('Processing', {
            'fields': ('processed_by',)
        }),
        ('Verification', {
            'fields': ('verification_method',)
        }),
    )
    
    actions = ['process_requests', 'complete_requests', 'reject_requests']
    
    def process_requests(self, request, queryset):
        for dsr in queryset.filter(status='pending'):
            dsr.process(request.user)
        self.message_user(request, f"{queryset.count()} requests marked as processing.")
    process_requests.short_description = "Start processing selected requests"
    
    def complete_requests(self, request, queryset):
        for dsr in queryset.filter(status='processing'):
            dsr.complete()
        self.message_user(request, f"{queryset.count()} requests completed.")
    complete_requests.short_description = "Complete selected requests"
    
    def reject_requests(self, request, queryset):
        for dsr in queryset:
            dsr.reject("Rejected by administrator")
        self.message_user(request, f"{queryset.count()} requests rejected.")
    reject_requests.short_description = "Reject selected requests"

@admin.register(BreachNotification)
class BreachNotificationAdmin(admin.ModelAdmin):
    list_display = ['breach_number', 'severity', 'status', 'detected_at', 'affected_users_count']
    list_filter = ['severity', 'status', 'detected_at']
    search_fields = ['breach_number', 'description']
    readonly_fields = ['breach_number', 'detected_at']
    
    fieldsets = (
        ('Breach Info', {
            'fields': ('breach_number', 'severity', 'status')
        }),
        ('Description', {
            'fields': ('description', 'affected_data', 'affected_users_count')
        }),
        ('Timeline', {
            'fields': ('detected_at', 'authorities_notified_at', 'users_notified_at', 'resolved_at')
        }),
        ('Investigation', {
            'fields': ('root_cause', 'impact_assessment')
        }),
        ('Remediation', {
            'fields': ('remediation_steps',)
        }),
        ('Notifications', {
            'fields': ('notified_authorities', 'notified_users')
        }),
    )
    
    actions = ['notify_authorities', 'notify_users', 'resolve_breaches']
    
    def notify_authorities(self, request, queryset):
        for breach in queryset:
            breach.notify_authorities()
        self.message_user(request, f"Authorities notified for {queryset.count()} breaches.")
    notify_authorities.short_description = "Notify authorities"
    
    def notify_users(self, request, queryset):
        for breach in queryset:
            breach.notify_affected_users()
        self.message_user(request, f"Users notified for {queryset.count()} breaches.")
    notify_users.short_description = "Notify affected users"
    
    def resolve_breaches(self, request, queryset):
        for breach in queryset:
            breach.resolve("Resolved via admin action")
        self.message_user(request, f"{queryset.count()} breaches marked as resolved.")
    resolve_breaches.short_description = "Mark as resolved"