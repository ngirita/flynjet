from django.contrib import admin
from django import forms
from django.utils.html import format_html
from django.urls import reverse
from django.shortcuts import redirect
from django.db import models as django_models
from django.contrib import messages
from django.core.validators import MinValueValidator
from .models import Enquiry
from .models import (
    AircraftCategory, AircraftManufacturer, Aircraft, AircraftImage,
    AircraftInterior360, AircraftSpecification, AircraftAvailability,
    AircraftMaintenance, AircraftStatusHistory, AircraftDocument,
    FleetStats
)
from apps.airports.models import Airport


class AircraftImageInline(admin.TabularInline):
    """Inline for multiple aircraft images with preview"""
    model = AircraftImage
    extra = 3
    fields = ['image', 'image_preview', 'caption', 'is_primary', 'sort_order']
    readonly_fields = ['image_preview']
    
    def image_preview(self, obj):
        if obj.id and obj.image:
            return format_html(
                '<img src="{}" style="max-height: 100px; max-width: 150px; object-fit: cover; border-radius: 4px;" />',
                obj.image.url
            )
        return "No image"
    image_preview.short_description = "Preview"


class AircraftSpecificationInline(admin.TabularInline):
    """Inline for additional specifications"""
    model = AircraftSpecification
    extra = 3
    fields = ['name', 'value', 'unit', 'icon', 'sort_order']


class AircraftInteriorInline(admin.TabularInline):
    """Inline for 360 interior views"""
    model = AircraftInterior360
    extra = 1
    readonly_fields = ['thumbnail_preview']
    
    def thumbnail_preview(self, obj):
        if obj.id and obj.thumbnail:
            return format_html(
                '<img src="{}" style="max-height: 100px; border-radius: 4px;" />',
                obj.thumbnail.url
            )
        return "No image"
    thumbnail_preview.short_description = "Preview"


class AircraftForm(forms.ModelForm):
    """Simplified form for aircraft with airport autocomplete"""
    
    # Add display fields as CharField with datalist
    base_airport_display = forms.CharField(
        label='Base Airport',
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'vTextField',
            'placeholder': 'Search by city or airport name (e.g., New York or JFK)',
            'autocomplete': 'off',
            'list': 'airport-list',
            'style': 'width: 300px;'
        }),
        help_text="Enter city name or airport name to search (e.g., 'New York' will show JFK, LGA, EWR)"
    )
    
    current_location_display = forms.CharField(
        label='Current Location',
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'vTextField',
            'placeholder': 'Search by city or airport name (e.g., London or LHR)',
            'autocomplete': 'off',
            'list': 'airport-list',
            'style': 'width: 300px;'
        }),
        help_text="Enter city name or airport name to search (e.g., 'London' will show LHR, LGW, LCY)"
    )
    
    # Add these hidden fields to store IATA codes
    base_airport = forms.CharField(
        widget=forms.HiddenInput(),
        required=False
    )
    
    current_location = forms.CharField(
        widget=forms.HiddenInput(),
        required=False
    )
    
    class Meta:
        model = Aircraft
        fields = [
            'registration_number', 'manufacturer', 'category', 'model', 'variant',
            'year_of_manufacture', 'passenger_capacity', 'crew_required',
            'cargo_capacity_kg', 'baggage_capacity_kg', 'max_range_nm',
            'cruise_speed_knots', 'length_m', 'wingspan_m', 'height_m',
            'cabin_height_m', 'cabin_width_m', 'cabin_length_m',
            'wifi_available', 'satellite_phone', 'entertainment_system',
            'galley', 'lavatory', 'shower', 'bedroom', 'conference_table',
            'status', 'thumbnail', 'total_flight_hours', 'is_active', 'is_featured', 'notes'
        ]
        widgets = {
            'registration_number': forms.TextInput(attrs={'class': 'vTextField', 'placeholder': 'e.g., N123AB'}),
            'manufacturer': forms.Select(attrs={'class': 'vTextField'}),
            'category': forms.Select(attrs={'class': 'vTextField'}),
            'model': forms.TextInput(attrs={'class': 'vTextField', 'placeholder': 'e.g., 737-800'}),
            'variant': forms.TextInput(attrs={'class': 'vTextField', 'placeholder': 'e.g., BBJ'}),
            'year_of_manufacture': forms.NumberInput(attrs={'class': 'vTextField'}),
            'passenger_capacity': forms.NumberInput(attrs={'class': 'vTextField', 'min': '0'}),
            'crew_required': forms.NumberInput(attrs={'class': 'vTextField'}),
            'cargo_capacity_kg': forms.NumberInput(attrs={'class': 'vTextField'}),
            'baggage_capacity_kg': forms.NumberInput(attrs={'class': 'vTextField'}),
            'max_range_nm': forms.NumberInput(attrs={'class': 'vTextField', 'placeholder': 'Nautical miles'}),
            'cruise_speed_knots': forms.NumberInput(attrs={'class': 'vTextField', 'placeholder': 'Knots'}),
            'length_m': forms.NumberInput(attrs={'class': 'vTextField', 'step': '0.01'}),
            'wingspan_m': forms.NumberInput(attrs={'class': 'vTextField', 'step': '0.01'}),
            'height_m': forms.NumberInput(attrs={'class': 'vTextField', 'step': '0.01'}),
            'cabin_height_m': forms.NumberInput(attrs={'class': 'vTextField', 'step': '0.01'}),
            'cabin_width_m': forms.NumberInput(attrs={'class': 'vTextField', 'step': '0.01'}),
            'cabin_length_m': forms.NumberInput(attrs={'class': 'vTextField', 'step': '0.01'}),
            'status': forms.Select(attrs={'class': 'vTextField'}),
            'thumbnail': forms.ClearableFileInput(attrs={'class': 'vTextField'}),
            'total_flight_hours': forms.NumberInput(attrs={'class': 'vTextField', 'step': '0.1'}),
            'notes': forms.Textarea(attrs={'class': 'vLargeTextField', 'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Add CSS class for better styling
        for field in self.fields:
            if not self.fields[field].widget.attrs.get('class'):
                self.fields[field].widget.attrs['class'] = 'vTextField'
        
        # If editing existing aircraft, populate display fields from stored IATA codes
        if self.instance and self.instance.pk:
            if self.instance.base_airport:
                try:
                    airport = Airport.objects.get(iata_code=self.instance.base_airport)
                    self.initial['base_airport_display'] = f"{airport.city} ({airport.iata_code})" if airport.city else f"{airport.name} ({airport.iata_code})"
                except Airport.DoesNotExist:
                    self.initial['base_airport_display'] = self.instance.base_airport
                self.initial['base_airport'] = self.instance.base_airport
            
            if self.instance.current_location:
                try:
                    airport = Airport.objects.get(iata_code=self.instance.current_location)
                    self.initial['current_location_display'] = f"{airport.city} ({airport.iata_code})" if airport.city else f"{airport.name} ({airport.iata_code})"
                except Airport.DoesNotExist:
                    self.initial['current_location_display'] = self.instance.current_location
                self.initial['current_location'] = self.instance.current_location
        
        # Hide aircraft field if pre-selected
        if 'initial' in kwargs and 'aircraft' in kwargs['initial']:
            self.fields['aircraft'].widget = forms.HiddenInput()
        
        # Dynamic field behavior based on category - FIXED
        category = None
        if self.instance and self.instance.pk:
            try:
                category = self.instance.category
            except AircraftCategory.DoesNotExist:
                category = None
        
        category_id = self.data.get('category') if self.data else None
        
        if category_id:
            try:
                cat = AircraftCategory.objects.get(id=category_id)
            except AircraftCategory.DoesNotExist:
                cat = None
        else:
            cat = category
        
        if cat and cat.category_type == 'cargo':
            # For cargo aircraft
            self.fields['passenger_capacity'].required = False
            self.fields['passenger_capacity'].widget.attrs['placeholder'] = '0 for cargo only'
            self.fields['passenger_capacity'].help_text = 'Set to 0 for cargo aircraft (can carry passengers if configured)'
            self.fields['passenger_capacity'].initial = 0
            
            # Cargo capacity is helpful but not required
            self.fields['cargo_capacity_kg'].required = False
            self.fields['cargo_capacity_kg'].help_text = 'Maximum cargo capacity in kg (optional)'
            
        else:
            # For passenger aircraft
            self.fields['passenger_capacity'].required = True
            self.fields['passenger_capacity'].widget.attrs['min'] = '1'
            self.fields['passenger_capacity'].help_text = 'Maximum number of passengers'
            self.fields['cargo_capacity_kg'].required = False
            self.fields['cargo_capacity_kg'].help_text = 'For cargo aircraft only'
    
    def clean(self):
        cleaned_data = super().clean()
        category = cleaned_data.get('category')
        passenger_capacity = cleaned_data.get('passenger_capacity')
        cargo_capacity_kg = cleaned_data.get('cargo_capacity_kg')
        
        if category:
            if category.category_type == 'cargo':
                # For cargo aircraft
                # Allow passenger_capacity to be 0 or positive
                if passenger_capacity is None:
                    passenger_capacity = 0
                    cleaned_data['passenger_capacity'] = 0
                
                # Cargo capacity is recommended but not required
                if not cargo_capacity_kg:
                    # Add a warning instead of error (optional)
                    pass
                    
            else:
                # For passenger aircraft (private_jet or helicopter)
                if not passenger_capacity or passenger_capacity <= 0:
                    self.add_error('passenger_capacity', 
                        'Passenger capacity must be at least 1 for passenger aircraft.')
        
        return cleaned_data
    
    def clean_base_airport(self):
        """Extract IATA code from display field"""
        value = self.cleaned_data.get('base_airport')
        if not value:
            return ''
        
        # If it's already a 3-letter code
        if len(value) == 3 and value.isalpha():
            return value.upper()
        
        # Try to find by name or city
        try:
            airport = Airport.objects.filter(
                django_models.Q(name__icontains=value) |
                django_models.Q(city__icontains=value) |
                django_models.Q(iata_code__iexact=value)
            ).first()
            if airport:
                return airport.iata_code
        except:
            pass
        
        return value
    
    def clean_current_location(self):
        """Extract IATA code from display field"""
        value = self.cleaned_data.get('current_location')
        if not value:
            return ''
        
        if len(value) == 3 and value.isalpha():
            return value.upper()
        
        try:
            airport = Airport.objects.filter(
                django_models.Q(name__icontains=value) |
                django_models.Q(city__icontains=value) |
                django_models.Q(iata_code__iexact=value)
            ).first()
            if airport:
                return airport.iata_code
        except:
            pass
        
        return value

@admin.register(AircraftCategory)
class AircraftCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'category_type', 'sort_order', 'is_active', 'aircraft_count']
    list_filter = ['category_type', 'is_active']
    search_fields = ['name', 'description']
    readonly_fields = ['slug']
    fieldsets = (
        (None, {
            'fields': ('category_type', 'name', 'slug', 'description')
        }),
        ('Media', {
            'fields': ('icon', 'image'),
            'classes': ('collapse',)
        }),
        ('Settings', {
            'fields': ('sort_order', 'is_active'),
            'classes': ('collapse',)
        }),
    )
    
    def aircraft_count(self, obj):
        return obj.aircraft.filter(is_active=True).count()
    aircraft_count.short_description = "Aircraft"
    
    def save_model(self, request, obj, form, change):
        if not obj.name:
            obj.name = dict(obj.CATEGORY_TYPES).get(obj.category_type, '')
        if not obj.slug:
            obj.slug = obj.category_type
        super().save_model(request, obj, form, change)


@admin.register(AircraftManufacturer)
class AircraftManufacturerAdmin(admin.ModelAdmin):
    list_display = ['name', 'country', 'founded_year', 'is_active', 'aircraft_count']
    list_filter = ['country', 'is_active']
    search_fields = ['name', 'description']
    prepopulated_fields = {'slug': ['name']}
    
    def aircraft_count(self, obj):
        return obj.aircraft.filter(is_active=True).count()
    aircraft_count.short_description = "Aircraft"


@admin.register(Aircraft)
class AircraftAdmin(admin.ModelAdmin):
    """Simplified Aircraft Admin with multiple images support"""
    
    form = AircraftForm
    
    list_display = [
        'registration_number', 'manufacturer', 'model', 'category',
        'passenger_capacity_display', 'status', 'base_airport_display', 
        'current_location_display', 'images_count', 'is_featured', 'thumbnail_preview'
    ]
    list_filter = ['status', 'category', 'manufacturer', 'is_featured', 'is_active']
    search_fields = ['registration_number', 'model', 'manufacturer__name']
    readonly_fields = ['created_at', 'updated_at', 'images_count']
    date_hierarchy = 'created_at'
    
    def passenger_capacity_display(self, obj):
        """Display passenger capacity with cargo indicator"""
        if obj.category and obj.category.category_type == 'cargo':
            if obj.passenger_capacity > 0:
                return format_html(
                    '<span style="color: #28a745;">{} pax + Cargo</span>',
                    obj.passenger_capacity
                )
            else:
                return format_html('<span style="color: #ffc107;">Cargo Only</span>')
        return f"{obj.passenger_capacity} pax"
    passenger_capacity_display.short_description = "Capacity"

    fieldsets = (
        ('Basic Information', {
            'fields': (
                'registration_number', 'manufacturer', 'category', 'model',
                'variant', 'year_of_manufacture'
            )
        }),
        ('Capacity', {
            'fields': (
                'passenger_capacity', 'crew_required', 'cargo_capacity_kg',
                'baggage_capacity_kg'
            )
        }),
        ('Performance', {
            'fields': ('max_range_nm', 'cruise_speed_knots')
        }),
        ('Dimensions', {
            'fields': (
                'length_m', 'wingspan_m', 'height_m', 'cabin_length_m',
                'cabin_width_m', 'cabin_height_m'
            )
        }),
        ('Amenities', {
            'fields': (
                'wifi_available', 'satellite_phone', 'entertainment_system',
                'galley', 'lavatory', 'shower', 'bedroom', 'conference_table'
            ),
            'classes': ('wide',)
        }),
        ('Images', {
            'fields': ('thumbnail',),
            'description': 'Main image for the aircraft. Additional images can be added below in the "Images" section.',
            'classes': ('wide',)
        }),
        ('Status & Location', {
            'fields': ('status', 'base_airport_display', 'current_location_display'),
            'description': 'Enter city name or airport name to search (e.g., "New York" will show JFK, LGA, EWR)'
        }),
        ('Operational', {
            'fields': ('total_flight_hours',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('is_active', 'is_featured', 'notes'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    inlines = [AircraftImageInline, AircraftSpecificationInline, AircraftInteriorInline]
    actions = ['mark_as_featured', 'mark_available', 'mark_maintenance', 'duplicate_aircraft', 'force_delete_aircraft']
    
    def images_count(self, obj):
        """Display count of images for this aircraft"""
        count = obj.images.count()
        if count > 0:
            return format_html(
                '<span style="background: #28a745; color: white; padding: 2px 8px; border-radius: 12px; font-size: 12px;">{}</span>',
                count
            )
        return format_html('<span style="color: #999;">0</span>')
    images_count.short_description = "Images"
    
    def base_airport_display(self, obj):
        """Display airport name with IATA code"""
        if obj.base_airport:
            try:
                airport = Airport.objects.get(iata_code=obj.base_airport)
                return format_html(
                    '<span title="{}" style="cursor: help;">{} ({})</span>',
                    airport.name,
                    airport.city,
                    airport.iata_code
                )
            except Airport.DoesNotExist:
                return obj.base_airport
        return "-"
    base_airport_display.short_description = "Base Airport"
    
    def current_location_display(self, obj):
        """Display airport name with IATA code"""
        if obj.current_location:
            try:
                airport = Airport.objects.get(iata_code=obj.current_location)
                return format_html(
                    '<span title="{}" style="cursor: help;">{} ({})</span>',
                    airport.name,
                    airport.city,
                    airport.iata_code
                )
            except Airport.DoesNotExist:
                return obj.current_location
        return "-"
    current_location_display.short_description = "Current Location"
    
    def thumbnail_preview(self, obj):
        if obj.thumbnail:
            return format_html(
                '<img src="{}" style="max-height: 40px; max-width: 60px; object-fit: cover; border-radius: 4px;" />',
                obj.thumbnail.url
            )
        return format_html('<span style="color: #999;">No image</span>')
    thumbnail_preview.short_description = "Thumbnail"
    
    def mark_as_featured(self, request, queryset):
        count = queryset.update(is_featured=True)
        self.message_user(request, f"{count} aircraft marked as featured.", messages.SUCCESS)
    mark_as_featured.short_description = "Mark selected as featured"
    
    def mark_available(self, request, queryset):
        count = 0
        for aircraft in queryset:
            aircraft.update_status('available', request.user)
            count += 1
        self.message_user(request, f"{count} aircraft marked as available.", messages.SUCCESS)
    mark_available.short_description = "Mark as available"
    
    def mark_maintenance(self, request, queryset):
        count = 0
        for aircraft in queryset:
            aircraft.update_status('maintenance', request.user)
            count += 1
        self.message_user(request, f"{count} aircraft marked for maintenance.", messages.SUCCESS)
    mark_maintenance.short_description = "Mark for maintenance"

    def force_delete_aircraft(self, request, queryset):
        """Force delete selected aircraft with all related objects, but keep contracts"""
        count = 0
        deleted_registrations = []
        
        for aircraft in queryset:
            registration = aircraft.registration_number
            try:
                # Delete all related objects (these have CASCADE)
                aircraft.images.all().delete()
                aircraft.interior_360.all().delete()
                aircraft.specifications.all().delete()
                aircraft.availability.all().delete()
                aircraft.maintenance_records.all().delete()
                aircraft.documents.all().delete()
                aircraft.status_history.all().delete()
                
                # For contracts - set aircraft to NULL (keep contracts, remove aircraft link)
                aircraft.contracts.update(aircraft=None)
                
                # For bookings - set aircraft to NULL (keep bookings, remove aircraft link)
                aircraft.bookings.update(aircraft=None)
                
                # For enquiries - set aircraft to NULL (keep enquiries, remove aircraft link)
                aircraft.enquiries.update(aircraft=None)
                
                # Finally delete the aircraft
                aircraft.delete()
                
                count += 1
                deleted_registrations.append(registration)
                
            except Exception as e:
                self.message_user(request, f"Error deleting {registration}: {str(e)}", level='ERROR')
        
        if count > 0:
            self.message_user(request, f"Successfully deleted {count} aircraft: {', '.join(deleted_registrations)}", level='SUCCESS')
    
    force_delete_aircraft.short_description = "Force delete selected aircraft (with all related data)"
    
    def duplicate_aircraft(self, request, queryset):
        """Duplicate selected aircraft"""
        for aircraft in queryset:
            new_aircraft = Aircraft.objects.create(
                registration_number=f"{aircraft.registration_number}_COPY",
                manufacturer=aircraft.manufacturer,
                category=aircraft.category,
                model=aircraft.model,
                variant=aircraft.variant,
                year_of_manufacture=aircraft.year_of_manufacture,
                passenger_capacity=aircraft.passenger_capacity,
                crew_required=aircraft.crew_required,
                cargo_capacity_kg=aircraft.cargo_capacity_kg,
                baggage_capacity_kg=aircraft.baggage_capacity_kg,
                max_range_nm=aircraft.max_range_nm,
                cruise_speed_knots=aircraft.cruise_speed_knots,
                length_m=aircraft.length_m,
                wingspan_m=aircraft.wingspan_m,
                height_m=aircraft.height_m,
                cabin_height_m=aircraft.cabin_height_m,
                cabin_width_m=aircraft.cabin_width_m,
                cabin_length_m=aircraft.cabin_length_m,
                wifi_available=aircraft.wifi_available,
                satellite_phone=aircraft.satellite_phone,
                entertainment_system=aircraft.entertainment_system,
                galley=aircraft.galley,
                lavatory=aircraft.lavatory,
                shower=aircraft.shower,
                bedroom=aircraft.bedroom,
                conference_table=aircraft.conference_table,
                status=aircraft.status,
                base_airport=aircraft.base_airport,
                current_location=aircraft.current_location,
                total_flight_hours=0,
                is_active=aircraft.is_active,
                notes=f"Duplicated from {aircraft.registration_number}",
            )
            # Copy images
            for img in aircraft.images.all():
                AircraftImage.objects.create(
                    aircraft=new_aircraft,
                    image=img.image,
                    caption=f"Copy: {img.caption}",
                    is_primary=img.is_primary,
                    sort_order=img.sort_order
                )
        self.message_user(request, f"{queryset.count()} aircraft duplicated.", messages.SUCCESS)
    duplicate_aircraft.short_description = "Duplicate selected aircraft"
    
    def get_queryset(self, request):
        """Optimize queryset with image count"""
        return super().get_queryset(request).select_related('manufacturer', 'category').prefetch_related('images')
    
    class Media:
        css = {
            'all': ('admin/css/fleet-admin.css',)
        }
        js = (
            'admin/js/fleet-autocomplete.js',
        )

@admin.register(AircraftMaintenance)
class AircraftMaintenanceAdmin(admin.ModelAdmin):
    list_display = [
        'aircraft', 'title', 'maintenance_type', 'status',
        'scheduled_start', 'estimated_cost_usd', 'maintenance_location_display'
    ]
    list_filter = ['maintenance_type', 'status', 'scheduled_start']
    search_fields = ['aircraft__registration_number', 'title', 'work_order_number']
    readonly_fields = ['created_at', 'updated_at', 'completed_at']
    date_hierarchy = 'scheduled_start'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('aircraft', 'maintenance_type', 'status', 'title', 'description')
        }),
        ('Schedule', {
            'fields': ('scheduled_start', 'scheduled_end', 'actual_start', 'actual_end')
        }),
        ('Location', {
            'fields': ('maintenance_location', 'maintenance_facility'),
            'description': 'Enter IATA code for maintenance location (e.g., JFK, LHR)'
        }),
        ('Costs', {
            'fields': ('estimated_cost_usd', 'actual_cost_usd', 'currency')
        }),
        ('Personnel', {
            'fields': ('technician_name', 'technician_license', 'supervisor_name'),
            'classes': ('collapse',)
        }),
        ('Parts & Documentation', {
            'fields': ('parts_used', 'work_order_number', 'report_document', 'completion_certificate'),
            'classes': ('collapse',)
        }),
        ('Results', {
            'fields': ('findings', 'recommendations', 'next_maintenance_due', 'next_maintenance_type'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at', 'completed_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['start_maintenance', 'complete_maintenance']
    
    def maintenance_location_display(self, obj):
        """Display airport name for maintenance location"""
        if obj.maintenance_location:
            try:
                airport = Airport.objects.get(iata_code=obj.maintenance_location)
                return format_html(
                    '<span title="{}">{} ({})</span>',
                    airport.name,
                    airport.city,
                    airport.iata_code
                )
            except Airport.DoesNotExist:
                return obj.maintenance_location
        return "-"
    maintenance_location_display.short_description = "Location"
    
    def start_maintenance(self, request, queryset):
        for maintenance in queryset:
            if maintenance.status == 'scheduled':
                maintenance.start_maintenance()
        self.message_user(request, f"{queryset.count()} maintenance records started.", messages.SUCCESS)
    start_maintenance.short_description = "Start selected maintenance"
    
    def complete_maintenance(self, request, queryset):
        for maintenance in queryset:
            if maintenance.status == 'in_progress':
                maintenance.complete_maintenance()
        self.message_user(request, f"{queryset.count()} maintenance records completed.", messages.SUCCESS)
    complete_maintenance.short_description = "Complete selected maintenance"
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('aircraft', 'aircraft__manufacturer')


@admin.register(AircraftDocument)
class AircraftDocumentAdmin(admin.ModelAdmin):
    list_display = ['aircraft', 'title', 'document_type', 'issue_date', 'expiry_date', 'is_approved', 'is_expired_display']
    list_filter = ['document_type', 'is_approved', 'issue_date']
    search_fields = ['aircraft__registration_number', 'title', 'document_number']
    readonly_fields = ['created_at', 'updated_at', 'approved_at']
    date_hierarchy = 'issue_date'
    
    fieldsets = (
        (None, {
            'fields': ('aircraft', 'document_type', 'title', 'document_number', 'file')
        }),
        ('Dates', {
            'fields': ('issue_date', 'expiry_date', 'issuing_authority')
        }),
        ('Approval', {
            'fields': ('is_approved', 'approved_by', 'approved_at'),
            'classes': ('collapse',)
        }),
        ('Notes', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['approve_documents', 'send_expiry_reminder']
    
    def is_expired_display(self, obj):
        if obj.is_expired():
            return format_html('<span style="color: #dc3545;">Expired</span>')
        days = obj.days_until_expiry()
        if days is not None and days <= 30:
            return format_html('<span style="color: #ffc107;">Expires in {} days</span>', days)
        return format_html('<span style="color: #28a745;">Valid</span>')
    is_expired_display.short_description = "Status"
    
    def approve_documents(self, request, queryset):
        from django.utils import timezone
        count = 0
        for doc in queryset:
            if not doc.is_approved:
                doc.is_approved = True
                doc.approved_by = request.user
                doc.approved_at = timezone.now()
                doc.save()
                count += 1
        self.message_user(request, f"{count} documents approved.", messages.SUCCESS)
    approve_documents.short_description = "Approve selected documents"
    
    def send_expiry_reminder(self, request, queryset):
        from django.core.mail import send_mail
        from django.conf import settings
        
        count = 0
        for doc in queryset:
            if doc.expiry_date and doc.days_until_expiry() <= 30 and doc.days_until_expiry() > 0:
                send_mail(
                    f'Document Expiry Notice - {doc.aircraft.registration_number}',
                    f'Document {doc.title} for aircraft {doc.aircraft.registration_number} expires on {doc.expiry_date}.',
                    settings.DEFAULT_FROM_EMAIL,
                    [settings.MANAGEMENT_EMAIL],
                    fail_silently=True,
                )
                count += 1
        self.message_user(request, f"Reminders sent for {count} documents.", messages.SUCCESS)
    send_expiry_reminder.short_description = "Send expiry reminders"


@admin.register(AircraftAvailability)
class AircraftAvailabilityAdmin(admin.ModelAdmin):
    list_display = ['aircraft', 'start_datetime', 'end_datetime', 'is_available', 'reason']
    list_filter = ['is_available', 'start_datetime']
    search_fields = ['aircraft__registration_number', 'reason']
    date_hierarchy = 'start_datetime'
    
    fieldsets = (
        (None, {
            'fields': ('aircraft', 'start_datetime', 'end_datetime', 'is_available', 'reason', 'booking')
        }),
    )


@admin.register(AircraftStatusHistory)
class AircraftStatusHistoryAdmin(admin.ModelAdmin):
    list_display = ['aircraft', 'old_status', 'new_status', 'changed_by', 'created_at']
    list_filter = ['old_status', 'new_status', 'created_at']
    search_fields = ['aircraft__registration_number', 'reason']
    readonly_fields = ['aircraft', 'old_status', 'new_status', 'changed_by', 'reason', 'created_at']
    date_hierarchy = 'created_at'
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Enquiry)
class EnquiryAdmin(admin.ModelAdmin):
    list_display = ['enquiry_number', 'get_full_name', 'email', 'aircraft', 'passenger_count', 'status', 'created_at']
    list_filter = ['status', 'created_at', 'aircraft_category']
    search_fields = ['enquiry_number', 'first_name', 'last_name', 'email', 'phone']
    readonly_fields = ['enquiry_number', 'created_at', 'ip_address', 'user_agent']
    
    fieldsets = (
        ('Enquiry Information', {
            'fields': ('enquiry_number', 'status', 'aircraft', 'aircraft_category')
        }),
        ('Contact Details', {
            'fields': ('first_name', 'last_name', 'email', 'phone', 'country')
        }),
        ('Flight Details', {
            'fields': ('departure_airport', 'arrival_airport', 'preferred_departure_date', 
                      'preferred_return_date', 'flexible_dates')
        }),
        ('Passenger & Luggage', {
            'fields': ('passenger_count', 'luggage_count', 'luggage_weight_kg', 'special_luggage')
        }),
        ('Amenities & Requirements', {
            'fields': ('amenities', 'catering_requirements', 'special_requests')
        }),
        ('Additional Services', {
            'fields': ('ground_transportation', 'hotel_accommodation', 'pet_travel')
        }),
        ('Admin Notes', {
            'fields': ('notes', 'contract_sent_at', 'contract_expiry')
        }),
        ('Metadata', {
            'fields': ('ip_address', 'user_agent', 'source', 'created_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['mark_reviewed', 'mark_contract_sent', 'create_contract']
    
    def get_full_name(self, obj):
        return obj.get_full_name()
    get_full_name.short_description = "Name"
    
    def mark_reviewed(self, request, queryset):
        count = queryset.update(status='reviewed')
        self.message_user(request, f"{count} enquiries marked as reviewed.", messages.SUCCESS)
    mark_reviewed.short_description = "Mark as reviewed"
    
    def mark_contract_sent(self, request, queryset):
        from django.utils import timezone
        count = 0
        for enquiry in queryset:
            if enquiry.status in ['new', 'reviewed']:
                enquiry.status = 'contract_sent'
                enquiry.contract_sent_at = timezone.now()
                enquiry.save()
                count += 1
        self.message_user(request, f"{count} enquiries marked as contract sent.", messages.SUCCESS)
    mark_contract_sent.short_description = "Mark as contract sent"
    
    def create_contract(self, request, queryset):
        """Create contract from selected enquiries"""
        for enquiry in queryset:
            if enquiry.status in ['new', 'reviewed']:
                return redirect(reverse('admin:bookings_contract_add') + f'?enquiry={enquiry.id}')
        self.message_user(request, "No new enquiries selected.", level='ERROR')
    create_contract.short_description = "Create contract from enquiry"


@admin.register(FleetStats)
class FleetStatsAdmin(admin.ModelAdmin):
    list_display = ['date', 'total_aircraft', 'available_aircraft', 'in_maintenance', 'average_utilization_rate']
    list_filter = ['date']
    readonly_fields = ['created_at']
    date_hierarchy = 'date'
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False