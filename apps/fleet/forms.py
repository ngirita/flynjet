from django import forms
from .models import Enquiry, Aircraft, AircraftCategory, AircraftManufacturer, AircraftMaintenance, AircraftDocument
from apps.airports.models import Airport  # Add this import
from apps.airports.widgets import AirportAutocompleteWidget  # Add this import

class AircraftForm(forms.ModelForm):
    """Form for creating/editing aircraft with airport autocomplete"""
    
    # Hidden fields to store IATA codes
    base_airport_iata = forms.CharField(
        max_length=3,
        widget=forms.HiddenInput(),
        required=False
    )
    
    current_location_iata = forms.CharField(
        max_length=3,
        widget=forms.HiddenInput(),
        required=False
    )
    
    # Display fields for user-friendly input
    base_airport_display = forms.CharField(
        label='Base Airport',
        widget=AirportAutocompleteWidget(attrs={
            'placeholder': 'Search by city or airport name...',
            'class': 'form-control'
        }),
        required=False,
        help_text="Search by city or airport name (e.g., 'New York' or 'JFK')"
    )
    
    current_location_display = forms.CharField(
        label='Current Location',
        widget=AirportAutocompleteWidget(attrs={
            'placeholder': 'Search by city or airport name...',
            'class': 'form-control'
        }),
        required=False,
        help_text="Search by city or airport name (e.g., 'London' or 'LHR')"
    )
    
    class Meta:
        model = Aircraft
        fields = '__all__'
        widgets = {
            'manufacturer': forms.Select(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'model': forms.TextInput(attrs={'class': 'form-control'}),
            'registration_number': forms.TextInput(attrs={'class': 'form-control'}),
            'year_of_manufacture': forms.NumberInput(attrs={'class': 'form-control'}),
            'passenger_capacity': forms.NumberInput(attrs={'class': 'form-control'}),
            'crew_required': forms.NumberInput(attrs={'class': 'form-control'}),
            'max_range_nm': forms.NumberInput(attrs={'class': 'form-control'}),
            'cruise_speed_knots': forms.NumberInput(attrs={'class': 'form-control'}),
            'hourly_rate_usd': forms.NumberInput(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # If editing an existing aircraft, populate display fields
        if self.instance and self.instance.pk:
            # Base airport
            if self.instance.base_airport:
                try:
                    airport = Airport.objects.get(iata_code=self.instance.base_airport)
                    self.initial['base_airport_display'] = airport.short_display
                    self.initial['base_airport_iata'] = airport.iata_code
                except Airport.DoesNotExist:
                    self.initial['base_airport_display'] = self.instance.base_airport
                    self.initial['base_airport_iata'] = self.instance.base_airport
            
            # Current location
            if self.instance.current_location:
                try:
                    airport = Airport.objects.get(iata_code=self.instance.current_location)
                    self.initial['current_location_display'] = airport.short_display
                    self.initial['current_location_iata'] = airport.iata_code
                except Airport.DoesNotExist:
                    self.initial['current_location_display'] = self.instance.current_location
                    self.initial['current_location_iata'] = self.instance.current_location
    
    def clean(self):
        cleaned_data = super().clean()
        
        # Handle base airport
        base_iata = cleaned_data.get('base_airport_iata')
        base_display = cleaned_data.get('base_airport_display')
        
        if base_display and not base_iata:
            import re
            match = re.search(r'\(([A-Z]{3})\)', base_display)
            if match:
                base_iata = match.group(1)
                cleaned_data['base_airport_iata'] = base_iata
            else:
                raise forms.ValidationError("Please select a valid airport from the suggestions.")
        
        if base_iata:
            try:
                Airport.objects.get(iata_code=base_iata)
                cleaned_data['base_airport'] = base_iata
            except Airport.DoesNotExist:
                raise forms.ValidationError(f"Airport '{base_iata}' not found in our database.")
        
        # Handle current location
        location_iata = cleaned_data.get('current_location_iata')
        location_display = cleaned_data.get('current_location_display')
        
        if location_display and not location_iata:
            import re
            match = re.search(r'\(([A-Z]{3})\)', location_display)
            if match:
                location_iata = match.group(1)
                cleaned_data['current_location_iata'] = location_iata
            else:
                raise forms.ValidationError("Please select a valid airport from the suggestions.")
        
        if location_iata:
            try:
                Airport.objects.get(iata_code=location_iata)
                cleaned_data['current_location'] = location_iata
            except Airport.DoesNotExist:
                raise forms.ValidationError(f"Airport '{location_iata}' not found in our database.")
        
        return cleaned_data


class AircraftSearchForm(forms.Form):
    """Form for searching aircraft with airport selection"""
    
    passengers = forms.IntegerField(
        required=False,
        min_value=1,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Number of passengers'})
    )
    date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    category = forms.ModelChoiceField(
        queryset=AircraftCategory.objects.filter(is_active=True),
        required=False,
        empty_label="All Categories",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    min_range = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Minimum range (nm)'})
    )
    max_price = forms.DecimalField(
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Max price per hour'})
    )
    from_airport = forms.CharField(
        required=False,
        max_length=3,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'From airport (IATA)'}),
        help_text="IATA code (e.g., JFK)"
    )
    to_airport = forms.CharField(
        required=False,
        max_length=3,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'To airport (IATA)'}),
        help_text="IATA code (e.g., LHR)"
    )


class AircraftMaintenanceForm(forms.ModelForm):
    """Form for scheduling maintenance with airport autocomplete"""
    
    # Hidden field for IATA code
    maintenance_location_iata = forms.CharField(
        max_length=3,
        widget=forms.HiddenInput(),
        required=False
    )
    
    # Display field for user-friendly input
    maintenance_location_display = forms.CharField(
        label='Maintenance Location',
        widget=AirportAutocompleteWidget(attrs={
            'placeholder': 'Search by city or airport name...',
            'class': 'form-control'
        }),
        required=False,
        help_text="Search by city or airport name (e.g., 'New York' or 'JFK')"
    )
    
    class Meta:
        model = AircraftMaintenance
        fields = [
            'aircraft', 'maintenance_type', 'title', 'description',
            'scheduled_start', 'scheduled_end', 'maintenance_location',
            'maintenance_facility', 'estimated_cost_usd'
        ]
        widgets = {
            'aircraft': forms.Select(attrs={'class': 'form-control'}),
            'maintenance_type': forms.Select(attrs={'class': 'form-control'}),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'scheduled_start': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'scheduled_end': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'maintenance_facility': forms.TextInput(attrs={'class': 'form-control'}),
            'estimated_cost_usd': forms.NumberInput(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # If editing existing maintenance, populate display field
        if self.instance and self.instance.pk and self.instance.maintenance_location:
            try:
                airport = Airport.objects.get(iata_code=self.instance.maintenance_location)
                self.initial['maintenance_location_display'] = airport.short_display
                self.initial['maintenance_location_iata'] = airport.iata_code
            except Airport.DoesNotExist:
                self.initial['maintenance_location_display'] = self.instance.maintenance_location
                self.initial['maintenance_location_iata'] = self.instance.maintenance_location
    
    def clean(self):
        cleaned_data = super().clean()
        
        # Handle maintenance location
        location_iata = cleaned_data.get('maintenance_location_iata')
        location_display = cleaned_data.get('maintenance_location_display')
        
        if location_display and not location_iata:
            import re
            match = re.search(r'\(([A-Z]{3})\)', location_display)
            if match:
                location_iata = match.group(1)
                cleaned_data['maintenance_location_iata'] = location_iata
            else:
                raise forms.ValidationError("Please select a valid airport from the suggestions.")
        
        if location_iata:
            try:
                Airport.objects.get(iata_code=location_iata)
                cleaned_data['maintenance_location'] = location_iata
            except Airport.DoesNotExist:
                raise forms.ValidationError(f"Airport '{location_iata}' not found in our database.")
        
        return cleaned_data


class AircraftDocumentForm(forms.ModelForm):
    """Form for uploading aircraft documents"""
    
    class Meta:
        model = AircraftDocument
        fields = ['document_type', 'title', 'document_number', 'file', 'issue_date', 'expiry_date', 'notes']
        widgets = {
            'document_type': forms.Select(attrs={'class': 'form-control'}),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'document_number': forms.TextInput(attrs={'class': 'form-control'}),
            'file': forms.FileInput(attrs={'class': 'form-control'}),
            'issue_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'expiry_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class AircraftCategoryForm(forms.ModelForm):
    """Form for aircraft categories"""
    
    class Meta:
        model = AircraftCategory
        fields = ['name', 'slug', 'category_type', 'description', 'icon', 'image', 'sort_order', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'slug': forms.TextInput(attrs={'class': 'form-control'}),
            'category_type': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'icon': forms.FileInput(attrs={'class': 'form-control'}),
            'image': forms.FileInput(attrs={'class': 'form-control'}),
            'sort_order': forms.NumberInput(attrs={'class': 'form-control'}),
        }


class AircraftManufacturerForm(forms.ModelForm):
    """Form for aircraft manufacturers"""
    
    class Meta:
        model = AircraftManufacturer
        fields = ['name', 'slug', 'logo', 'country', 'website', 'description', 'founded_year']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'slug': forms.TextInput(attrs={'class': 'form-control'}),
            'logo': forms.FileInput(attrs={'class': 'form-control'}),
            'country': forms.TextInput(attrs={'class': 'form-control'}),
            'website': forms.URLInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'founded_year': forms.NumberInput(attrs={'class': 'form-control'}),
        }


class CargoEnquiryForm(forms.ModelForm):
    """Specialized form for cargo aircraft enquiries"""
    
    class Meta:
        model = Enquiry
        fields = [
            'first_name', 'last_name', 'email', 'phone', 'country',
            'departure_airport', 'arrival_airport',
            'preferred_departure_date', 'preferred_return_date', 'flexible_dates',
            'cargo_weight_kg', 'special_luggage', 'special_requests'
        ]
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'John'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Doe'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'john@example.com'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+1 234 567 8900'}),
            'country': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'United States'}),
            'departure_airport': AirportAutocompleteWidget(attrs={
                'class': 'form-control',
                'placeholder': 'Search by city or airport name...'
            }),
            'arrival_airport': AirportAutocompleteWidget(attrs={
                'class': 'form-control',
                'placeholder': 'Search by city or airport name...'
            }),
            'preferred_departure_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'preferred_return_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'flexible_dates': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'cargo_weight_kg': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'Total cargo weight in kg'}),
            'special_luggage': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Describe any special cargo requirements...'}),
            'special_requests': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Any special handling requirements?'}),
        }
        labels = {
            'cargo_weight_kg': 'Cargo Weight (kg)',
            'special_luggage': 'Special Cargo Description',
        }
        help_texts = {
            'cargo_weight_kg': 'Total weight of cargo to be transported',
            'special_luggage': 'Describe any oversized, hazardous, or special cargo items',
        }
    
    cargo_weight_kg = forms.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        required=True,
        widget=forms.NumberInput(attrs={
            'class': 'form-control', 
            'step': '0.01', 
            'placeholder': 'Total cargo weight in kg'
        }),
        help_text='Total weight of cargo to be transported'
    )
    
    def __init__(self, *args, **kwargs):
        self.aircraft = kwargs.pop('aircraft', None)
        super().__init__(*args, **kwargs)
        
        # Set aircraft category to cargo
        if self.aircraft:
            self.fields['aircraft_category'] = forms.CharField(
                initial='cargo',
                widget=forms.HiddenInput()
            )
    
    def clean_cargo_weight_kg(self):
        cargo_weight = self.cleaned_data.get('cargo_weight_kg')
        if cargo_weight and self.aircraft and self.aircraft.cargo_capacity_kg:
            if cargo_weight > float(self.aircraft.cargo_capacity_kg):
                raise forms.ValidationError(
                    f'Cargo weight exceeds aircraft capacity of {self.aircraft.cargo_capacity_kg} kg.'
                )
        return cargo_weight


class PassengerEnquiryForm(forms.ModelForm):
    """Regular form for passenger aircraft enquiries"""
    
    class Meta:
        model = Enquiry
        fields = [
            'first_name', 'last_name', 'email', 'phone', 'country',
            'departure_airport', 'arrival_airport',
            'preferred_departure_date', 'preferred_return_date', 'flexible_dates',
            'passenger_count', 'luggage_count', 'luggage_weight_kg', 'special_luggage',
            'catering_requirements', 'special_requests',
            'ground_transportation', 'hotel_accommodation', 'pet_travel'
        ]
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'John'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Doe'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'john@example.com'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+1 234 567 8900'}),
            'country': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'United States'}),
            'departure_airport': AirportAutocompleteWidget(attrs={
                'class': 'form-control',
                'placeholder': 'Search by city or airport name...'
            }),
            'arrival_airport': AirportAutocompleteWidget(attrs={
                'class': 'form-control',
                'placeholder': 'Search by city or airport name...'
            }),
            'preferred_departure_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'preferred_return_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'flexible_dates': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'passenger_count': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'placeholder': 'Number of passengers'}),
            'luggage_count': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'placeholder': 'Number of bags'}),
            'luggage_weight_kg': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'Total luggage weight'}),
            'special_luggage': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Golf clubs, skis, etc.'}),
            'catering_requirements': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Dietary restrictions, meal preferences'}),
            'special_requests': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Any special requests?'}),
            'ground_transportation': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'hotel_accommodation': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'pet_travel': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.aircraft = kwargs.pop('aircraft', None)
        super().__init__(*args, **kwargs)
        
        if self.aircraft:
            # Set max passengers based on aircraft capacity
            self.fields['passenger_count'].widget.attrs['max'] = self.aircraft.passenger_capacity
            self.fields['passenger_count'].help_text = f'Maximum {self.aircraft.passenger_capacity} passengers'
    
    def clean_passenger_count(self):
        passenger_count = self.cleaned_data.get('passenger_count')
        if passenger_count and self.aircraft:
            if passenger_count > self.aircraft.passenger_capacity:
                raise forms.ValidationError(
                    f'Passenger count exceeds aircraft capacity of {self.aircraft.passenger_capacity}.'
                )
        return passenger_count