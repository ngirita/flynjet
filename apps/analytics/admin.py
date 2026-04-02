from django.contrib import admin
from .models import AnalyticsEvent, DailyMetric, Report, Dashboard

@admin.register(AnalyticsEvent)
class AnalyticsEventAdmin(admin.ModelAdmin):
    list_display = ['event_id', 'event_type', 'user', 'timestamp', 'session_id']
    list_filter = ['event_type', 'timestamp']
    search_fields = ['event_id', 'user__email', 'session_id']
    readonly_fields = ['event_id', 'timestamp']
    
    fieldsets = (
        ('Event Info', {
            'fields': ('event_id', 'event_type', 'timestamp', 'user', 'anonymous_id', 'session_id')
        }),
        ('Page Info', {
            'fields': ('url', 'referrer')
        }),
        ('Device Info', {
            'fields': ('user_agent', 'ip_address', 'device_type', 'browser', 'os')
        }),
        ('Location', {
            'fields': ('country', 'city')
        }),
        ('Data', {
            'fields': ('data',)
        }),
    )
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False

@admin.register(DailyMetric)
class DailyMetricAdmin(admin.ModelAdmin):
    list_display = ['date', 'new_users', 'active_users', 'total_bookings', 'revenue', 'page_views']
    list_filter = ['date']
    search_fields = ['date']
    readonly_fields = ['created_at']
    
    fieldsets = (
        ('Date', {
            'fields': ('date',)
        }),
        ('User Metrics', {
            'fields': ('new_users', 'active_users', 'returning_users')
        }),
        ('Booking Metrics', {
            'fields': ('total_bookings', 'completed_bookings', 'cancelled_bookings', 
                      'booking_value', 'average_booking_value')
        }),
        ('Revenue Metrics', {
            'fields': ('revenue', 'refunds', 'net_revenue')
        }),
        ('Payment Metrics', {
            'fields': ('payment_success', 'payment_failed', 'payment_method_breakdown')
        }),
        ('Fleet Metrics', {
            'fields': ('flights_completed', 'flight_hours', 'fleet_utilization')
        }),
        ('Traffic Metrics', {
            'fields': ('page_views', 'unique_visitors', 'bounce_rate', 'avg_session_duration')
        }),
        ('Support Metrics', {
            'fields': ('support_tickets', 'avg_response_time', 'satisfaction_score')
        }),
        ('Metadata', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    def has_add_permission(self, request):
        return False

@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ['name', 'report_number', 'report_type', 'format', 'frequency', 'last_run']
    list_filter = ['report_type', 'format', 'frequency']
    search_fields = ['name', 'report_number', 'description']
    readonly_fields = ['report_number', 'created_at', 'last_run']
    
    fieldsets = (
        ('Report Info', {
            'fields': ('name', 'report_number', 'report_type', 'description')
        }),
        ('Configuration', {
            'fields': ('parameters', 'format', 'frequency')
        }),
        ('Schedule', {
            'fields': ('next_run', 'last_run')
        }),
        ('Recipients', {
            'fields': ('recipients',)
        }),
        ('File', {
            'fields': ('generated_file', 'file_size')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Owner', {
            'fields': ('created_by', 'created_at')
        }),
    )
    
    actions = ['generate_reports', 'send_reports']
    
    def generate_reports(self, request, queryset):
        for report in queryset:
            report.generate()
        self.message_user(request, f"{queryset.count()} reports generated.")
    generate_reports.short_description = "Generate selected reports"
    
    def send_reports(self, request, queryset):
        for report in queryset:
            report.deliver()
        self.message_user(request, f"{queryset.count()} reports sent.")
    send_reports.short_description = "Send selected reports"

@admin.register(Dashboard)
class DashboardAdmin(admin.ModelAdmin):
    list_display = ['name', 'user', 'dashboard_type', 'is_shared', 'created_at']
    list_filter = ['dashboard_type', 'is_shared']
    search_fields = ['name', 'user__email']
    readonly_fields = ['share_token', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Dashboard Info', {
            'fields': ('name', 'user', 'dashboard_type')
        }),
        ('Configuration', {
            'fields': ('widgets', 'layout', 'filters')
        }),
        ('Sharing', {
            'fields': ('is_shared', 'share_token', 'share_expiry')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )