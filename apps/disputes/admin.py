from django.contrib import admin
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.urls import path  # Add this import
from django.shortcuts import redirect  # Add this import
from .models import Dispute, DisputeMessage, DisputeEvidence, DisputeResolution, DisputeAnalytics

User = get_user_model()

@admin.register(Dispute)
class DisputeAdmin(admin.ModelAdmin):
    list_display = ['dispute_number', 'user', 'booking', 'dispute_type', 'status', 'priority', 'filed_at']
    list_filter = ['dispute_type', 'status', 'priority', 'filed_at']
    search_fields = ['dispute_number', 'user__email', 'booking__booking_reference', 'subject']
    readonly_fields = ['dispute_number', 'filed_at', 'resolved_at']

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('all/', self.admin_site.admin_view(self.view_all_disputes), name='disputes_all'),
        ]
        return custom_urls + urls
    
    def view_all_disputes(self, request):
        # Redirect to changelist with no filters
        return redirect('admin:disputes_dispute_changelist')
    
    # Remove any default filtering - show all disputes
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # Don't filter by default - show all
        return qs
    
    fieldsets = (
        ('Dispute Info', {
            'fields': ('dispute_number', 'user', 'booking', 'payment')
        }),
        ('Details', {
            'fields': ('dispute_type', 'status', 'priority', 'subject', 'description')
        }),
        ('Financial', {
            'fields': ('disputed_amount', 'currency', 'refund_issued', 'refund_amount', 'refund_transaction_id')
        }),
        ('Timeline', {
            'fields': ('filed_at', 'response_deadline', 'resolved_at')
        }),
        ('Assignment', {
            'fields': ('assigned_to', 'assigned_at')
        }),
        ('Resolution', {
            'fields': ('resolution_notes', 'outcome', 'resolved_by')
        }),
        ('Evidence', {
            'fields': ('evidence_files',)
        }),
        ('Metadata', {
            'fields': ('ip_address', 'user_agent'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['assign_to_me', 'mark_urgent', 'send_reminder']
    
    def assign_to_me(self, request, queryset):
        queryset.update(assigned_to=request.user, assigned_at=timezone.now(), status='investigating')
        self.message_user(request, f"{queryset.count()} disputes assigned to you.")
    assign_to_me.short_description = "Assign selected disputes to me"
    
    def mark_urgent(self, request, queryset):
        queryset.update(priority='urgent')
        self.message_user(request, f"{queryset.count()} disputes marked as urgent.")
    mark_urgent.short_description = "Mark as urgent"
    
    def send_reminder(self, request, queryset):
        for dispute in queryset:
            # Send reminder email
            from django.core.mail import send_mail
            send_mail(
                f"Dispute {dispute.dispute_number} requires attention",
                f"Please review dispute {dispute.dispute_number} assigned to you.",
                'info@flynjet.com',
                [dispute.assigned_to.email] if dispute.assigned_to else [admin.email for admin in User.objects.filter(is_staff=True)],
                fail_silently=False,
            )
        self.message_user(request, f"Reminders sent for {queryset.count()} disputes.")
    send_reminder.short_description = "Send reminder emails"

@admin.register(DisputeMessage)
class DisputeMessageAdmin(admin.ModelAdmin):
    list_display = ['dispute', 'sender', 'is_staff', 'created_at', 'is_read']
    list_filter = ['is_staff', 'is_read', 'created_at']
    search_fields = ['dispute__dispute_number', 'sender__email', 'message']
    readonly_fields = ['created_at', 'read_at']

@admin.register(DisputeEvidence)
class DisputeEvidenceAdmin(admin.ModelAdmin):
    list_display = ['dispute', 'evidence_type', 'uploaded_by', 'uploaded_at']
    list_filter = ['evidence_type', 'uploaded_at']
    search_fields = ['dispute__dispute_number', 'description']
    readonly_fields = ['uploaded_at']

@admin.register(DisputeResolution)
class DisputeResolutionAdmin(admin.ModelAdmin):
    list_display = ['dispute', 'resolution_type', 'accepted_by_customer', 'proposed_by', 'proposed_at']
    list_filter = ['resolution_type', 'accepted_by_customer']
    search_fields = ['dispute__dispute_number', 'description']
    readonly_fields = ['proposed_at', 'accepted_at']

@admin.register(DisputeAnalytics)
class DisputeAnalyticsAdmin(admin.ModelAdmin):
    list_display = ['date', 'total_disputes', 'open_disputes', 'resolved_disputes', 'total_disputed_amount']
    list_filter = ['date']
    search_fields = ['date']
    readonly_fields = ['created_at']