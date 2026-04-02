from django import forms
from django.forms import formset_factory
from django.utils import timezone
from .models import Booking, BookingPassenger
from apps.fleet.models import Aircraft
from apps.airports.models import Airport
import re

class BookingForm(forms.ModelForm):
    aircraft = forms.ModelChoiceField(
        queryset=Aircraft.objects.filter(status='available'),
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    # Hidden fields to store IATA codes
    departure_airport_iata = forms.CharField(
        max_length=3,
        widget=forms.HiddenInput(),
        required=False
    )
    
    arrival_airport_iata = forms.CharField(
        max_length=3,
        widget=forms.HiddenInput(),
        required=False
    )
    
    # Use CharField with Select widget to avoid choices validation
    departure_airport_display = forms.CharField(
        label='Departure Airport',
        widget=forms.Select(attrs={
            'class': 'form-control airport-autocomplete',
            'placeholder': 'Search by city or airport name...',
            'data-autocomplete-url': '/airports/autocomplete/'
        }),
        required=True,
        help_text="Start typing city name or airport name (e.g., 'New York' or 'JFK')"
    )
    
    arrival_airport_display = forms.CharField(
        label='Arrival Airport',
        widget=forms.Select(attrs={
            'class': 'form-control airport-autocomplete',
            'placeholder': 'Search by city or airport name...',
            'data-autocomplete-url': '/airports/autocomplete/'
        }),
        required=True,
        help_text="Start typing city name or airport name (e.g., 'London' or 'LHR')"
    )
    
    catering_options = forms.MultipleChoiceField(
        choices=[
            ('standard', 'Standard Meal'),
            ('vegetarian', 'Vegetarian'),
            ('vegan', 'Vegan'),
            ('kosher', 'Kosher'),
            ('halal', 'Halal'),
            ('gluten_free', 'Gluten Free'),
            ('diabetic', 'Diabetic'),
            ('children', 'Children Meal'),
            ('champagne', 'Champagne Service'),
            ('caviar', 'Caviar Service'),
        ],
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        label="Catering Options"
    )
    
    class Meta:
        model = Booking
        fields = [
            'aircraft', 'flight_type',
            'departure_datetime', 'arrival_datetime', 'passenger_count',
            'special_requests', 'dietary_requirements', 'medical_requirements',
            'catering_options', 'ground_transportation_required',
            'hotel_required', 'insurance_purchased'
        ]
        widgets = {
            'departure_datetime': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'arrival_datetime': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'special_requests': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'dietary_requirements': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'medical_requirements': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'passenger_count': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),  # Changed min to 0
            'ground_transportation_required': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'hotel_required': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'insurance_purchased': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'flight_type': forms.Select(attrs={'class': 'form-control'}),
        }
    
    def clean_passenger_count(self):
        """Validate passenger count based on aircraft type"""
        passenger_count = self.cleaned_data.get('passenger_count')
        aircraft = self.cleaned_data.get('aircraft')
        
        if aircraft and aircraft.category and aircraft.category.category_type == 'cargo':
            # For cargo aircraft, passenger count should be 0
            if passenger_count and passenger_count > 0:
                raise forms.ValidationError("Cargo aircraft cannot carry passengers. Set passenger count to 0.")
            return 0
        
        # For passenger aircraft, passenger count must be at least 1
        if not passenger_count or passenger_count < 1:
            raise forms.ValidationError("Please specify the number of passengers (minimum 1).")
        
        return passenger_count
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # If editing an existing booking, populate display fields
        if self.instance and self.instance.pk:
            # Populate departure airport
            if self.instance.departure_airport:
                try:
                    airport = Airport.objects.get(iata_code=self.instance.departure_airport)
                    display_text = f"{airport.city} ({airport.iata_code})" if airport.city else f"{airport.name} ({airport.iata_code})"
                    self.initial['departure_airport_display'] = display_text
                    self.initial['departure_airport_iata'] = airport.iata_code
                except Airport.DoesNotExist:
                    pass
            
            # Populate arrival airport
            if self.instance.arrival_airport:
                try:
                    airport = Airport.objects.get(iata_code=self.instance.arrival_airport)
                    display_text = f"{airport.city} ({airport.iata_code})" if airport.city else f"{airport.name} ({airport.iata_code})"
                    self.initial['arrival_airport_display'] = display_text
                    self.initial['arrival_airport_iata'] = airport.iata_code
                except Airport.DoesNotExist:
                    pass
        
        # Hide aircraft field if pre-selected
        if 'initial' in kwargs and 'aircraft' in kwargs['initial']:
            self.fields['aircraft'].widget = forms.HiddenInput()
    
    def clean(self):
        cleaned_data = super().clean()
        
        # DEBUG: Print what we received
        print("=" * 50)
        print("CLEAN METHOD - Received data:")
        print(f"departure_airport_display: {cleaned_data.get('departure_airport_display')}")
        print(f"arrival_airport_display: {cleaned_data.get('arrival_airport_display')}")
        print(f"departure_airport_iata: {cleaned_data.get('departure_airport_iata')}")
        print(f"arrival_airport_iata: {cleaned_data.get('arrival_airport_iata')}")
        print("=" * 50)
        
        # Get IATA codes from hidden fields (set by JavaScript)
        departure_iata = cleaned_data.get('departure_airport_iata')
        arrival_iata = cleaned_data.get('arrival_airport_iata')
        
        print(f"Final departure IATA: {departure_iata}")
        print(f"Final arrival IATA: {arrival_iata}")
        
        # Validate that we have IATA codes
        if not departure_iata:
            raise forms.ValidationError("Please select a departure airport from the suggestions.")
        
        if not arrival_iata:
            raise forms.ValidationError("Please select an arrival airport from the suggestions.")
        
        # Verify airports exist in our database
        try:
            departure_airport = Airport.objects.get(iata_code=departure_iata)
            cleaned_data['departure_airport'] = departure_iata
            print(f"✓ Departure airport found: {departure_airport.name}")
        except Airport.DoesNotExist:
            raise forms.ValidationError(f"Departure airport '{departure_iata}' not found in our database.")
        
        try:
            arrival_airport = Airport.objects.get(iata_code=arrival_iata)
            cleaned_data['arrival_airport'] = arrival_iata
            print(f"✓ Arrival airport found: {arrival_airport.name}")
        except Airport.DoesNotExist:
            raise forms.ValidationError(f"Arrival airport '{arrival_iata}' not found in our database.")
        
        # Validate airports are different
        if departure_iata and arrival_iata and departure_iata == arrival_iata:
            raise forms.ValidationError("Departure and arrival airports must be different.")
        
        # Validate dates
        departure_time = cleaned_data.get('departure_datetime')
        arrival_time = cleaned_data.get('arrival_datetime')
        
        print(f"Departure time: {departure_time}")
        print(f"Arrival time: {arrival_time}")
        
        if departure_time and arrival_time and departure_time >= arrival_time:
            raise forms.ValidationError("Arrival time must be after departure time.")
        
        if departure_time and departure_time < timezone.now():
            raise forms.ValidationError("Departure time must be in the future.")
        
        min_advance = timezone.timedelta(hours=2)
        if departure_time and departure_time < timezone.now() + min_advance:
            raise forms.ValidationError(f"Bookings must be made at least {min_advance.seconds // 3600} hours in advance.")
        
        return cleaned_data


class PassengerForm(forms.ModelForm):
    """Form for individual passenger details"""
    
    class Meta:
        model = BookingPassenger
        fields = [
            'title', 'first_name', 'last_name', 'date_of_birth',
            'nationality', 'passport_number', 'passport_expiry',
            'passport_country', 'email', 'phone_number',
            'dietary_requirements', 'medical_requirements', 'special_assistance',
            'seat_number', 'baggage_count', 'baggage_weight_kg',
            'emergency_contact_name', 'emergency_contact_phone',
            'emergency_contact_relation'
        ]
        widgets = {
            'title': forms.Select(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First name'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last name'}),
            'date_of_birth': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'nationality': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nationality'}),
            'passport_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Passport number'}),
            'passport_expiry': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'passport_country': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Passport country'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email address'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Phone number'}),
            'dietary_requirements': forms.Textarea(attrs={'rows': 2, 'class': 'form-control', 'placeholder': 'Any dietary requirements?'}),
            'medical_requirements': forms.Textarea(attrs={'rows': 2, 'class': 'form-control', 'placeholder': 'Any medical requirements?'}),
            'special_assistance': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'seat_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Seat preference'}),
            'baggage_count': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'baggage_weight_kg': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'emergency_contact_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Emergency contact name'}),
            'emergency_contact_phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Emergency contact phone'}),
            'emergency_contact_relation': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Relation'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make certain fields required
        self.fields['title'].required = True
        self.fields['first_name'].required = True
        self.fields['last_name'].required = True
        self.fields['date_of_birth'].required = True
        self.fields['nationality'].required = True
        self.fields['passport_number'].required = True
        self.fields['passport_expiry'].required = True
        self.fields['passport_country'].required = True
        self.fields['emergency_contact_name'].required = True
        self.fields['emergency_contact_phone'].required = True
        self.fields['emergency_contact_relation'].required = True
        
        # Make baggage fields optional with default 0
        self.fields['baggage_count'].required = False
        self.fields['baggage_weight_kg'].required = False
        self.fields['baggage_count'].initial = 0
        self.fields['baggage_weight_kg'].initial = 0
        
        # Optional fields
        self.fields['email'].required = False
        self.fields['phone_number'].required = False
        self.fields['seat_number'].required = False
        self.fields['dietary_requirements'].required = False
        self.fields['medical_requirements'].required = False
        self.fields['special_assistance'].required = False
        
        # Add help texts
        self.fields['passport_number'].help_text = "Enter your passport number exactly as it appears on your passport"
        self.fields['passport_expiry'].help_text = "Passport must be valid for at least 6 months after travel"
        self.fields['baggage_count'].help_text = "Number of checked bags (enter 0 if none)"
        self.fields['baggage_weight_kg'].help_text = "Total weight in kg (enter 0 if none)"
            
    def clean(self):
        cleaned_data = super().clean()
        passport_expiry = cleaned_data.get('passport_expiry')
        date_of_birth = cleaned_data.get('date_of_birth')
        
        # Validate passport expiry
        if passport_expiry and passport_expiry < timezone.now().date():
            raise forms.ValidationError("Passport has expired. Please provide a valid passport.")
        
        # Validate age (must be at least 2 years old)
        if date_of_birth:
            today = timezone.now().date()
            age = today.year - date_of_birth.year - ((today.month, today.day) < (date_of_birth.month, date_of_birth.day))
            if age < 2:
                raise forms.ValidationError("Passenger must be at least 2 years old.")
        
        return cleaned_data