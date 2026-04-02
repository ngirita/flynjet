from django.contrib import admin
from django.utils.html import format_html
from .models import Airport

@admin.register(Airport)
class AirportAdmin(admin.ModelAdmin):
    list_display = ['iata_code', 'name', 'city', 'country', 'is_active']
    list_filter = ['country', 'is_active']
    search_fields = ['iata_code', 'name', 'city', 'country']
    list_editable = ['is_active']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Airport Codes', {
            'fields': ('iata_code', 'icao_code')
        }),
        ('Airport Information', {
            'fields': ('name', 'city', 'country', 'country_code')
        }),
        ('Geographical Data', {
            'fields': ('latitude', 'longitude', 'timezone', 'elevation_ft'),
            'classes': ('collapse',)
        }),
        ('Contact Information', {
            'fields': ('website', 'phone'),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )