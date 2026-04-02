from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, DetailView, View  # Add View here
from django.db import models
from django.contrib import messages  # Add messages import
from decimal import Decimal  # Add Decimal import
from django.template.loader import render_to_string
from django.conf import settings
from django.core.mail import send_mail, EmailMultiAlternatives
from django.utils import timezone
from django.db.models import Q
import json
from .models import Aircraft, AircraftCategory, Enquiry  # Add Enquiry import
from apps.airports.models import Airport
from .forms import PassengerEnquiryForm, CargoEnquiryForm
from apps.bookings.models import Booking
import logging
from django.views.decorators.csrf import csrf_protect
from django.utils.decorators import method_decorator

logger = logging.getLogger(__name__)
# fleet/views.py - Add this to your existing views

def submit_enquiry(request):
    """Handle enquiry submission with different forms for cargo vs passenger"""
    if request.method == 'POST':
        aircraft_id = request.POST.get('aircraft_id')
        aircraft = get_object_or_404(Aircraft, id=aircraft_id) if aircraft_id else None
        
        # Determine which form to use based on aircraft category
        if aircraft and aircraft.category.category_type == 'cargo':
            form = CargoEnquiryForm(request.POST, aircraft=aircraft)
            is_cargo = True
        else:
            form = PassengerEnquiryForm(request.POST, aircraft=aircraft)
            is_cargo = False
        
        if form.is_valid():
            enquiry = form.save(commit=False)
            if aircraft:
                enquiry.aircraft = aircraft
                enquiry.aircraft_category = aircraft.category.category_type
            else:
                enquiry.aircraft_category = request.POST.get('aircraft_category', 'private_jet')
            
            # Set IP and user agent
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                enquiry.ip_address = x_forwarded_for.split(',')[0]
            else:
                enquiry.ip_address = request.META.get('REMOTE_ADDR')
            enquiry.user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]
            enquiry.source = 'website'
            
            enquiry.save()
            
            messages.success(request, 'Your enquiry has been submitted successfully! We will contact you within 24 hours.')
            
            # Redirect based on enquiry type
            if is_cargo:
                return redirect('fleet:cargo_thank_you')
            else:
                return redirect('fleet:thank_you')
        else:
            messages.error(request, 'Please correct the errors below.')
            context = {
                'form': form,
                'aircraft': aircraft,
                'is_cargo': is_cargo,
            }
            if aircraft:
                return render(request, 'fleet/aircraft_detail.html', context)
            else:
                return render(request, 'fleet/enquiry_form.html', context)
    
    return redirect('fleet:list')

def cargo_thank_you(request):
    """Thank you page for cargo enquiries"""
    return render(request, 'fleet/cargo_thank_you.html')

def thank_you(request):
    """Thank you page for passenger enquiries"""
    return render(request, 'fleet/thank_you.html')

class AircraftListView(ListView):
    model = Aircraft
    template_name = 'fleet/aircraft_list.html'
    context_object_name = 'aircraft'
    paginate_by = 12
    
    def get_queryset(self):
        queryset = Aircraft.objects.filter(is_active=True, status='available')
        
        # Filter by category
        category_slug = self.request.GET.get('category')
        if category_slug:
            queryset = queryset.filter(category__slug=category_slug)
        
        # Filter by passenger capacity
        min_passengers = self.request.GET.get('min_passengers')
        if min_passengers:
            queryset = queryset.filter(passenger_capacity__gte=min_passengers)
        
        # Filter by range
        min_range = self.request.GET.get('min_range')
        if min_range:
            queryset = queryset.filter(max_range_nm__gte=min_range)
        
        # Search
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                models.Q(manufacturer__name__icontains=search) |
                models.Q(model__icontains=search) |
                models.Q(registration_number__icontains=search)
            )
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = AircraftCategory.objects.filter(is_active=True)
        return context


class AircraftDetailView(DetailView):
    model = Aircraft
    template_name = 'fleet/aircraft_detail.html'
    context_object_name = 'aircraft'
    slug_field = 'id'
    
    def get_queryset(self):
        """Override to prefetch related images for better performance"""
        return Aircraft.objects.filter(is_active=True).prefetch_related('images')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['related_aircraft'] = Aircraft.objects.filter(
            category=self.object.category,
            is_active=True
        ).exclude(id=self.object.id).prefetch_related('images')[:3]
        
        # Add base airport details if available
        if self.object.base_airport:
            try:
                context['base_airport'] = Airport.objects.get(iata_code=self.object.base_airport)
            except Airport.DoesNotExist:
                context['base_airport'] = None
        
        # Add current location details
        if self.object.current_location:
            try:
                context['current_location'] = Airport.objects.get(iata_code=self.object.current_location)
            except Airport.DoesNotExist:
                context['current_location'] = None
        
        # Debug: Print images count to console
        images_count = self.object.images.count()
        print(f"Aircraft {self.object.registration_number} has {images_count} images")
        for img in self.object.images.all():
            print(f"  - Image URL: {img.image.url if img.image else 'No image'}")
        
        return context


class CategoryListView(ListView):
    model = AircraftCategory
    template_name = 'fleet/category_list.html'
    context_object_name = 'categories'
    
    def get_queryset(self):
        return AircraftCategory.objects.filter(is_active=True)


class CategoryDetailView(DetailView):
    model = AircraftCategory
    template_name = 'fleet/category_detail.html'
    context_object_name = 'category'
    slug_field = 'slug'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['aircraft'] = Aircraft.objects.filter(
            category=self.object,
            is_active=True,
            status='available'
        )
        return context


# In your fleet/views.py, update the check_availability function:

def check_availability(request):
    """Check aircraft availability for given dates with airport name support."""
    if request.method == 'GET':
        from_airport_code = request.GET.get('from')
        to_airport_code = request.GET.get('to')
        date = request.GET.get('date')
        passengers = request.GET.get('passengers', 1)
        
        try:
            passengers = int(passengers)
        except ValueError:
            passengers = 1
        
        # Get airport objects for display
        departure_airport = None
        arrival_airport = None
        
        if from_airport_code:
            try:
                departure_airport = Airport.objects.get(iata_code=from_airport_code)
            except Airport.DoesNotExist:
                pass
        
        if to_airport_code:
            try:
                arrival_airport = Airport.objects.get(iata_code=to_airport_code)
            except Airport.DoesNotExist:
                pass
        
        # Find available aircraft - PREFETCH IMAGES
        available_aircraft = Aircraft.objects.filter(
            is_active=True,
            status='available',
            passenger_capacity__gte=passengers
        ).prefetch_related('images')  # Add this line to prefetch images
        
        # Check availability for the date
        if date:
            try:
                from datetime import datetime
                search_date = datetime.strptime(date, '%Y-%m-%d').date()
                
                # Find aircraft that are already booked on this date
                booked_aircraft = Booking.objects.filter(
                    Q(departure_datetime__date=search_date) |
                    Q(arrival_datetime__date=search_date),
                    status__in=['confirmed', 'paid', 'in_progress']
                ).values_list('aircraft_id', flat=True)
                
                # Exclude booked aircraft
                available_aircraft = available_aircraft.exclude(id__in=booked_aircraft)
                
            except ValueError:
                pass
        
        context = {
            'aircraft': available_aircraft,
            'from_airport_code': from_airport_code,
            'to_airport_code': to_airport_code,
            'departure_airport': departure_airport,
            'arrival_airport': arrival_airport,
            'date': date,
            'passengers': passengers,
            'search_performed': bool(from_airport_code and to_airport_code and date)
        }
        
        return render(request, 'fleet/availability.html', context)
    
    # If not GET request, redirect to aircraft list
    return redirect('fleet:aircraft_list')

@method_decorator(csrf_protect, name='dispatch')
class SubmitEnquiryView(View):
    """Handle enquiry form submission"""
    
    def post(self, request):
        try:
            # Get form data
            aircraft_id = request.POST.get('aircraft_id')
            aircraft = None
            if aircraft_id:
                try:
                    aircraft = Aircraft.objects.get(id=aircraft_id)
                except Aircraft.DoesNotExist:
                    pass
            
            # Get passenger count and determine if cargo
            passenger_count = int(request.POST.get('passenger_count', 1))
            is_cargo = request.POST.get('is_cargo_enquiry') == 'true'
            
            # For cargo, set passenger_count to 0
            if is_cargo:
                passenger_count = 0
            
            # Get cargo weight if applicable
            cargo_weight_kg = Decimal(request.POST.get('cargo_weight_kg', '0')) if is_cargo else None
            
            # Create enquiry record
            enquiry = Enquiry.objects.create(
                aircraft=aircraft,
                first_name=request.POST.get('first_name', ''),
                last_name=request.POST.get('last_name', ''),
                email=request.POST.get('email', ''),
                phone=request.POST.get('phone', ''),
                country=request.POST.get('country', ''),
                departure_airport=request.POST.get('departure_airport', '').upper() if request.POST.get('departure_airport') else '',
                arrival_airport=request.POST.get('arrival_airport', '').upper() if request.POST.get('arrival_airport') else '',
                preferred_departure_date=request.POST.get('preferred_departure_date') or None,
                preferred_return_date=request.POST.get('preferred_return_date') or None,
                flexible_dates=request.POST.get('flexible_dates') == 'on',
                passenger_count=passenger_count,
                luggage_count=int(request.POST.get('luggage_count', 0)),
                luggage_weight_kg=Decimal(request.POST.get('luggage_weight_kg', '0')),
                special_luggage=request.POST.get('special_luggage', ''),
                amenities=request.POST.getlist('amenities'),
                catering_requirements=request.POST.get('catering_requirements', ''),
                special_requests=request.POST.get('special_requests', ''),
                ground_transportation=request.POST.get('ground_transportation') == 'true',
                hotel_accommodation=request.POST.get('hotel_accommodation') == 'true',
                pet_travel=request.POST.get('pet_travel') == 'true',
                cargo_weight_kg=cargo_weight_kg,
                ip_address=request.META.get('REMOTE_ADDR', ''),
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
                source='website'
            )
            
            # Send notification email to admin
            self.send_admin_notification(enquiry)
            
            # Send confirmation email to client
            self.send_client_confirmation(enquiry)
            
            messages.success(request, 'Thank you for your enquiry! We will get back to you within 24 hours.')
            
            # Redirect based on enquiry type
            if is_cargo:
                return redirect('fleet:cargo_thank_you')
            else:
                return redirect('fleet:thank_you')
                
        except Exception as e:
            logger.error(f"Enquiry submission error: {e}")
            messages.error(request, f'There was an error submitting your enquiry. Please try again or contact us directly.')
            return redirect('fleet:list')
    
    def send_admin_notification(self, enquiry):
        """Send email notification to admin"""
        subject = f"New Charter Enquiry - {enquiry.enquiry_number}"
        
        # Get airport objects for display
        departure_airport_obj = None
        arrival_airport_obj = None
        
        if enquiry.departure_airport:
            try:
                departure_airport_obj = Airport.objects.get(iata_code=enquiry.departure_airport)
            except Airport.DoesNotExist:
                pass
        
        if enquiry.arrival_airport:
            try:
                arrival_airport_obj = Airport.objects.get(iata_code=enquiry.arrival_airport)
            except Airport.DoesNotExist:
                pass
        
        context = {
            'enquiry': enquiry,
            'admin_url': f"{settings.SITE_URL}/admin/fleet/enquiry/{enquiry.id}/change/",
            'departure_airport_obj': departure_airport_obj,
            'arrival_airport_obj': arrival_airport_obj,
        }
        
        html_message = render_to_string('emails/admin_enquiry_notification.html', context)
        plain_message = f"""
New Enquiry Received: {enquiry.enquiry_number}

Client: {enquiry.get_full_name()}
Email: {enquiry.email}
Phone: {enquiry.phone}
Aircraft: {enquiry.aircraft.manufacturer.name} {enquiry.aircraft.model if enquiry.aircraft else 'Any'}
Type: {'Cargo' if enquiry.is_cargo else 'Passenger'}

Flight Details:
From: {enquiry.departure_airport or 'Any'}
To: {enquiry.arrival_airport or 'Any'}
Preferred Date: {enquiry.preferred_departure_date or 'Flexible'}

Passengers: {enquiry.passenger_count}
Luggage: {enquiry.luggage_count} pieces ({enquiry.luggage_weight_kg} kg)
{'Cargo Weight: ' + str(enquiry.cargo_weight_kg) + ' kg' if enquiry.cargo_weight_kg else ''}

Special Requests: {enquiry.special_requests or 'None'}

View and respond: {settings.SITE_URL}/admin/fleet/enquiry/{enquiry.id}/change/
"""
        
        send_mail(
            subject,
            plain_message,
            settings.DEFAULT_FROM_EMAIL,
            [settings.ADMIN_EMAIL],
            html_message=html_message,
            fail_silently=False,
        )

    def send_client_confirmation(self, enquiry):
        """Send confirmation email to client"""
        subject = f"Enquiry Received - {enquiry.enquiry_number}"
        
        # Get airport objects for display
        departure_airport_obj = None
        arrival_airport_obj = None
        
        if enquiry.departure_airport:
            try:
                departure_airport_obj = Airport.objects.get(iata_code=enquiry.departure_airport)
            except Airport.DoesNotExist:
                pass
        
        if enquiry.arrival_airport:
            try:
                arrival_airport_obj = Airport.objects.get(iata_code=enquiry.arrival_airport)
            except Airport.DoesNotExist:
                pass
        
        context = {
            'enquiry': enquiry,
            'site_url': settings.SITE_URL,
            'departure_airport_obj': departure_airport_obj,
            'arrival_airport_obj': arrival_airport_obj,
        }
        
        html_message = render_to_string('emails/client_enquiry_confirmation.html', context)
        plain_message = f"""
Dear {enquiry.first_name},

Thank you for your enquiry ({enquiry.enquiry_number}). We have received your request and our team will get back to you with a personalized quote within 24 hours.

Enquiry Details:
- Type: {'Cargo Charter' if enquiry.cargo_weight_kg else 'Passenger Charter'}
- Aircraft: {enquiry.aircraft.manufacturer.name} {enquiry.aircraft.model if enquiry.aircraft else 'Any'}
- Passengers: {enquiry.passenger_count}
- From: {departure_airport_obj.name if departure_airport_obj else enquiry.departure_airport or 'Any'} ({departure_airport_obj.iata_code if departure_airport_obj else enquiry.departure_airport or 'Any'})
- To: {arrival_airport_obj.name if arrival_airport_obj else enquiry.arrival_airport or 'Any'} ({arrival_airport_obj.iata_code if arrival_airport_obj else enquiry.arrival_airport or 'Any'})
- Preferred Dates: {enquiry.preferred_departure_date or 'Flexible'}
{' - Cargo Weight: ' + str(enquiry.cargo_weight_kg) + ' kg' if enquiry.cargo_weight_kg else ''}

We look forward to helping you with your travel plans!

Regards,
FlynJet Team
"""
        
        send_mail(
            subject,
            plain_message,
            settings.DEFAULT_FROM_EMAIL,
            [enquiry.email],
            html_message=html_message,
            fail_silently=False,
        )