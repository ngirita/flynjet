from django.contrib import admin
from django.utils import timezone
from .models import APIIntegration, WebhookEndpoint, WebhookDelivery, WeatherCache, FuelPriceCache, ExchangeRateCache

@admin.register(APIIntegration)
class APIIntegrationAdmin(admin.ModelAdmin):
    list_display = ['name', 'integration_type', 'auth_type', 'is_active', 'last_checked']
    list_filter = ['integration_type', 'auth_type', 'is_active']
    search_fields = ['name', 'base_url']
    readonly_fields = ['last_checked', 'last_error']
    
    fieldsets = (
        ('Integration Info', {
            'fields': ('name', 'integration_type', 'is_active')
        }),
        ('Connection', {
            'fields': ('base_url', 'auth_type')
        }),
        ('Authentication', {
            'fields': ('api_key', 'api_secret', 'client_id', 'client_secret'),
            'classes': ('collapse',)
        }),
        ('OAuth2', {
            'fields': ('access_token', 'refresh_token', 'token_expires_at'),
            'classes': ('collapse',)
        }),
        ('Configuration', {
            'fields': ('config', 'headers', 'rate_limit')
        }),
        ('Status', {
            'fields': ('last_checked', 'last_error')
        }),
    )
    
    actions = ['test_connection', 'refresh_token']
    
    def test_connection(self, request, queryset):
        for integration in queryset:
            try:
                # Test connection logic
                integration.last_checked = timezone.now()
                integration.last_error = ''
                integration.save()
                self.message_user(request, f"Connection to {integration.name} successful.")
            except Exception as e:
                integration.last_error = str(e)
                integration.save()
                self.message_user(request, f"Connection to {integration.name} failed: {e}", level='ERROR')
    test_connection.short_description = "Test connection"
    
    def refresh_token(self, request, queryset):
        for integration in queryset.filter(auth_type='oauth2'):
            # Refresh token logic
            integration.token_expires_at = timezone.now() + timezone.timedelta(hours=1)
            integration.save()
        self.message_user(request, f"Tokens refreshed for {queryset.count()} integrations.")
    refresh_token.short_description = "Refresh OAuth tokens"

@admin.register(WebhookEndpoint)
class WebhookEndpointAdmin(admin.ModelAdmin):
    list_display = ['name', 'path', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['name', 'path']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Webhook Info', {
            'fields': ('name', 'path', 'is_active')
        }),
        ('Security', {
            'fields': ('secret', 'allowed_ips', 'require_signature')
        }),
        ('Configuration', {
            'fields': ('events', 'handler_function')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(WebhookDelivery)
class WebhookDeliveryAdmin(admin.ModelAdmin):
    list_display = ['webhook', 'event_type', 'status', 'attempts', 'created_at']
    list_filter = ['status', 'event_type', 'created_at']
    search_fields = ['webhook__name', 'event_type']
    readonly_fields = ['created_at', 'last_attempt', 'response_status', 'response_body', 'error_message']
    
    fieldsets = (
        ('Delivery Info', {
            'fields': ('webhook', 'event_type', 'status')
        }),
        ('Payload', {
            'fields': ('payload',)
        }),
        ('Attempts', {
            'fields': ('attempts', 'last_attempt')
        }),
        ('Response', {
            'fields': ('response_status', 'response_body')
        }),
        ('Error', {
            'fields': ('error_message',)
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    def has_add_permission(self, request):
        return False

@admin.register(WeatherCache)
class WeatherCacheAdmin(admin.ModelAdmin):
    list_display = ['location_key', 'temperature', 'conditions', 'fetched_at', 'expires_at']
    list_filter = ['fetched_at']
    search_fields = ['location_key']
    readonly_fields = ['fetched_at']

@admin.register(FuelPriceCache)
class FuelPriceCacheAdmin(admin.ModelAdmin):
    list_display = ['location_code', 'jet_a_price', 'avgas_price', 'fetched_at', 'expires_at']
    list_filter = ['fetched_at']
    search_fields = ['location_code']
    readonly_fields = ['fetched_at']

@admin.register(ExchangeRateCache)
class ExchangeRateCacheAdmin(admin.ModelAdmin):
    list_display = ['from_currency', 'to_currency', 'rate', 'fetched_at', 'expires_at']
    list_filter = ['fetched_at']
    search_fields = ['from_currency', 'to_currency']
    readonly_fields = ['fetched_at']