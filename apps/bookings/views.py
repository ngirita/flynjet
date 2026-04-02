from decimal import Decimal
from datetime import datetime, date
import json
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import redirect_to_login
from django.views.generic import ListView, DetailView, CreateView, UpdateView, FormView
from django.contrib import messages
from django.urls import reverse_lazy, reverse
from django.utils import timezone
from django.db.models import Q, Sum
from django.forms import formset_factory
from .models import Booking, Invoice, BookingHistory
from .forms import BookingForm, PassengerForm
from apps.fleet.models import Aircraft
from apps.airports.models import Airport  # Add this import
from apps.payments.models import Payment  # Add this import for total spent


class BookingListView(LoginRequiredMixin, ListView):
    model = Booking
    template_name = 'bookings/booking_list.html'
    context_object_name = 'bookings'
    paginate_by = 10
    
    def get_queryset(self):
        return Booking.objects.filter(user=self.request.user).order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        now = timezone.now()
        
        # Get all user bookings
        all_bookings = Booking.objects.filter(user=user)
        
        # Calculate total bookings
        context['total_bookings'] = all_bookings.exclude(status='draft').count()
        
        # Calculate upcoming bookings
        context['upcoming_bookings'] = all_bookings.filter(
            Q(status__in=['confirmed', 'paid', 'in_progress']),
            departure_datetime__gt=now
        ).count()
        
        # Calculate completed bookings
        context['completed_bookings'] = all_bookings.filter(status='completed').count()
        
        # ========== FIXED: Calculate total spent from booking.amount_paid ==========
        # This sums ALL money paid regardless of Payment record status
        total_spent = all_bookings.aggregate(
            total=Sum('amount_paid')
        )['total'] or Decimal('0')
        
        context['total_spent'] = total_spent
        context['now'] = now
        
        # Add airport objects
        for booking in context['bookings']:
            if booking.departure_airport:
                try:
                    booking.departure_airport_obj = Airport.objects.get(iata_code=booking.departure_airport)
                except Airport.DoesNotExist:
                    booking.departure_airport_obj = None
            
            if booking.arrival_airport:
                try:
                    booking.arrival_airport_obj = Airport.objects.get(iata_code=booking.arrival_airport)
                except Airport.DoesNotExist:
                    booking.arrival_airport_obj = None
        
        return context


class BookingDetailView(LoginRequiredMixin, DetailView):
    model = Booking
    template_name = 'bookings/booking_detail.html'
    context_object_name = 'booking'
    
    def get_queryset(self):
        return Booking.objects.filter(user=self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['now'] = timezone.now()
        
        # Add airport details for display
        booking = context['booking']
        
        if booking.departure_airport:
            try:
                context['departure_airport'] = Airport.objects.get(iata_code=booking.departure_airport)
            except Airport.DoesNotExist:
                context['departure_airport'] = None
                context['departure_airport_code'] = booking.departure_airport
        
        if booking.arrival_airport:
            try:
                context['arrival_airport'] = Airport.objects.get(iata_code=booking.arrival_airport)
            except Airport.DoesNotExist:
                context['arrival_airport'] = None
                context['arrival_airport_code'] = booking.arrival_airport
        
        return context


class BookingCreateView(LoginRequiredMixin, CreateView):
    model = Booking
    form_class = BookingForm
    template_name = 'bookings/booking_form.html'
    
    def get_initial(self):
        initial = super().get_initial()
        aircraft_id = self.request.GET.get('aircraft')
        if aircraft_id:
            initial['aircraft'] = aircraft_id
        return initial
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        aircraft_id = self.request.GET.get('aircraft')
        if aircraft_id:
            context['aircraft'] = get_object_or_404(Aircraft, id=aircraft_id)
        return context
    
    def form_valid(self, form):
        # Convert form data to JSON-serializable format
        booking_data = {}
        for key, value in form.cleaned_data.items():
            if key == 'aircraft':
                if value:
                    booking_data['aircraft'] = str(value.id)
                else:
                    booking_data['aircraft'] = None
            elif key == 'departure_airport':
                booking_data['departure_airport'] = value
            elif key == 'arrival_airport':
                booking_data['arrival_airport'] = value
            elif isinstance(value, (timezone.datetime, timezone.datetime.__class__)):
                booking_data[key] = value.isoformat() if value else None
            elif isinstance(value, date):
                booking_data[key] = value.isoformat() if value else None
            else:
                booking_data[key] = value
        
        # Add cargo weight if it exists in the form
        if hasattr(form, 'cargo_weight_kg') and form.cleaned_data.get('cargo_weight_kg'):
            booking_data['cargo_weight_kg'] = form.cleaned_data['cargo_weight_kg']
        
        # Store in session
        self.request.session['booking_data'] = booking_data
        
        # Store aircraft ID separately as backup
        if 'aircraft' in form.cleaned_data and form.cleaned_data['aircraft']:
            self.request.session['selected_aircraft'] = str(form.cleaned_data['aircraft'].id)
        else:
            aircraft_id = self.request.GET.get('aircraft')
            if aircraft_id:
                self.request.session['selected_aircraft'] = aircraft_id
        
        messages.success(self.request, 'Flight details saved. Please enter passenger information.')
        
        # Redirect to passenger details page
        return redirect('bookings:passenger_details')
    
    def form_invalid(self, form):
        return self.render_to_response(self.get_context_data(form=form))
    

class PassengerDetailsView(LoginRequiredMixin, FormView):
    template_name = 'bookings/passenger_details.html'
    
    def dispatch(self, request, *args, **kwargs):
        print("=" * 50)
        print("DISPATCH - Checking session")
        if 'booking_data' not in request.session:
            print("No booking_data in session!")
            messages.error(request, 'Please start your booking from the beginning.')
            return redirect('bookings:create')
        print("Session has booking_data")
        
        # Check if this is a cargo booking
        booking_data = request.session.get('booking_data', {})
        aircraft_id = request.session.get('selected_aircraft')
        
        if aircraft_id:
            try:
                aircraft = Aircraft.objects.get(id=aircraft_id)
                if aircraft.category.category_type == 'cargo':
                    # For cargo, skip passenger details and create booking directly
                    print("Cargo booking detected - skipping passenger details")
                    return self.create_cargo_booking(request)
            except Aircraft.DoesNotExist:
                pass
        
        return super().dispatch(request, *args, **kwargs)
    
    def create_cargo_booking(self, request):
        """Create cargo booking without passenger details"""
        booking_data = request.session.get('booking_data')
        aircraft_id = request.session.get('selected_aircraft')
        
        if not booking_data or not aircraft_id:
            messages.error(request, 'Booking data missing. Please start over.')
            return redirect('bookings:create')
        
        aircraft = get_object_or_404(Aircraft, id=aircraft_id)
        
        # Parse datetime strings back to datetime objects
        departure_datetime = booking_data.get('departure_datetime')
        arrival_datetime = booking_data.get('arrival_datetime')
        
        if isinstance(departure_datetime, str):
            departure_datetime = timezone.datetime.fromisoformat(departure_datetime)
        if isinstance(arrival_datetime, str):
            arrival_datetime = timezone.datetime.fromisoformat(arrival_datetime)
        
        # Calculate flight duration in hours
        flight_duration = (arrival_datetime - departure_datetime).total_seconds() / 3600
        
        # Get cargo weight from booking data or use default
        cargo_weight = booking_data.get('cargo_weight_kg', 0)
        
        # Calculate base price based on cargo weight and duration
        base_price = aircraft.hourly_rate_usd * Decimal(str(flight_duration))
        
        # For cargo, add weight-based pricing
        if cargo_weight > 0:
            weight_surcharge = (Decimal(str(cargo_weight)) / Decimal('1000')) * Decimal('100')  # $100 per 1000kg
            base_price += weight_surcharge
        
        fuel_surcharge = base_price * Decimal('0.15')
        handling_fee = Decimal('500.00')
        
        # Create the booking
        booking = Booking.objects.create(
            user=self.request.user,
            aircraft=aircraft,
            flight_type=booking_data.get('flight_type'),
            departure_airport=booking_data.get('departure_airport'),
            arrival_airport=booking_data.get('arrival_airport'),
            departure_datetime=departure_datetime,
            arrival_datetime=arrival_datetime,
            passenger_count=0,  # No passengers for cargo
            cargo_weight_kg=cargo_weight,
            special_requests=booking_data.get('special_requests', ''),
            base_price_usd=base_price,
            fuel_surcharge_usd=fuel_surcharge,
            handling_fee_usd=handling_fee,
            flight_duration_hours=Decimal(str(flight_duration)),
            amount_paid=Decimal('0.00'),
            payment_due_date=departure_datetime - timezone.timedelta(days=7),
            preferred_currency='USD',
            exchange_rate=Decimal('1.000000'),
            total_amount_preferred=Decimal('0.00'),
            status='pending',
            source='website'
        )
        
        booking.calculate_totals()
        booking.save()
        
        # Clear session data
        if 'booking_data' in self.request.session:
            del self.request.session['booking_data']
        if 'selected_aircraft' in self.request.session:
            del self.request.session['selected_aircraft']
        
        messages.success(self.request, f'Cargo booking {booking.booking_reference} created successfully!')
        return redirect('bookings:review', pk=booking.pk)
  
    def get_form(self, form_class=None):
        print("=" * 50)
        print("GET_FORM - Creating formset")
        booking_data = self.request.session.get('booking_data', {})
        passenger_count = booking_data.get('passenger_count', 1)
        print(f"Passenger count: {passenger_count}")
        
        # Create a formset with the appropriate number of forms
        PassengerFormSet = formset_factory(PassengerForm, extra=passenger_count, can_delete=False)
        
        if self.request.method in ('POST', 'PUT'):
            print("POST request - returning bound formset")
            return PassengerFormSet(self.request.POST, self.request.FILES)
        print("GET request - returning empty formset")
        return PassengerFormSet()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        booking_data = self.request.session.get('booking_data', {})
        
        # Get airport details for display
        departure_iata = booking_data.get('departure_airport')
        arrival_iata = booking_data.get('arrival_airport')
        
        if departure_iata:
            try:
                context['departure_airport'] = Airport.objects.get(iata_code=departure_iata)
            except Airport.DoesNotExist:
                context['departure_airport'] = None
                context['departure_airport_code'] = departure_iata
        
        if arrival_iata:
            try:
                context['arrival_airport'] = Airport.objects.get(iata_code=arrival_iata)
            except Airport.DoesNotExist:
                context['arrival_airport'] = None
                context['arrival_airport_code'] = arrival_iata
        
        context['booking_data'] = booking_data
        
        # Get aircraft details
        aircraft_id = self.request.session.get('selected_aircraft')
        if aircraft_id:
            context['aircraft'] = get_object_or_404(Aircraft, id=aircraft_id)
        
        return context
    
    def post(self, request, *args, **kwargs):
        print("=" * 50)
        print("POST METHOD CALLED")
        print(f"POST data: {request.POST}")
        return super().post(request, *args, **kwargs)
    
    def form_valid(self, form):
        print("=" * 50)
        print("FORM_VALID CALLED - Form is valid!")
        print(f"Form data: {form.cleaned_data}")
        
        # Create the booking
        booking_data = self.request.session.get('booking_data')
        aircraft_id = self.request.session.get('selected_aircraft')
        
        if not booking_data or not aircraft_id:
            print("Missing booking_data or aircraft_id")
            messages.error(self.request, 'Booking data missing. Please start over.')
            return redirect('bookings:create')
        
        aircraft = get_object_or_404(Aircraft, id=aircraft_id)
        print(f"Aircraft found: {aircraft}")
        
        # Parse datetime strings back to datetime objects
        departure_datetime = booking_data.get('departure_datetime')
        arrival_datetime = booking_data.get('arrival_datetime')
        
        if isinstance(departure_datetime, str):
            departure_datetime = timezone.datetime.fromisoformat(departure_datetime)
        if isinstance(arrival_datetime, str):
            arrival_datetime = timezone.datetime.fromisoformat(arrival_datetime)
        
        print(f"Departure: {departure_datetime}")
        print(f"Arrival: {arrival_datetime}")
        
        # Calculate flight duration in hours
        flight_duration = (arrival_datetime - departure_datetime).total_seconds() / 3600
        print(f"Flight duration: {flight_duration} hours")
        
        # Calculate base price from aircraft hourly rate
        base_price = aircraft.hourly_rate_usd * Decimal(str(flight_duration))
        print(f"Base price: {base_price}")
        
        # Calculate fuel surcharge (15% of base price)
        fuel_surcharge = base_price * Decimal('0.15')
        
        # Fixed handling fee
        handling_fee = Decimal('500.00')
        
        # Calculate catering cost based on passenger count and selected options
        catering_cost = Decimal('0.00')
        if booking_data.get('catering_options'):
            catering_cost = Decimal(str(booking_data.get('passenger_count', 1))) * Decimal('50.00')
        
        # Calculate insurance premium if purchased
        insurance_premium = Decimal('0.00')
        if booking_data.get('insurance_purchased'):
            insurance_premium = Decimal('250.00')
        
        # Create the booking with ALL required fields
        booking = Booking.objects.create(
            user=self.request.user,
            aircraft=aircraft,
            flight_type=booking_data.get('flight_type'),
            departure_airport=booking_data.get('departure_airport'),
            arrival_airport=booking_data.get('arrival_airport'),
            departure_datetime=departure_datetime,
            arrival_datetime=arrival_datetime,
            passenger_count=booking_data.get('passenger_count'),
            special_requests=booking_data.get('special_requests', ''),
            dietary_requirements=booking_data.get('dietary_requirements', ''),
            medical_requirements=booking_data.get('medical_requirements', ''),
            catering_options=booking_data.get('catering_options', []),
            ground_transportation_required=booking_data.get('ground_transportation_required', False),
            hotel_required=booking_data.get('hotel_required', False),
            insurance_purchased=booking_data.get('insurance_purchased', False),
            insurance_premium=insurance_premium,
            
            # Pricing fields
            base_price_usd=base_price,
            fuel_surcharge_usd=fuel_surcharge,
            handling_fee_usd=handling_fee,
            catering_cost_usd=catering_cost,
            overnight_charge_usd=Decimal('0.00'),
            cleaning_charge_usd=Decimal('250.00'),
            insurance_cost_usd=insurance_premium,
            discount_amount_usd=Decimal('0.00'),
            
            # Flight details
            flight_duration_hours=Decimal(str(flight_duration)),
            flight_distance_nm=1000,
            flight_distance_km=1852,
            
            # Payment
            amount_paid=Decimal('0.00'),
            payment_due_date=departure_datetime - timezone.timedelta(days=7),
            
            # Currency fields
            preferred_currency='USD',
            exchange_rate=Decimal('1.000000'),
            total_amount_preferred=Decimal('0.00'),
            
            status='pending',
            source='website'
        )
        
        print(f"Booking created with ID: {booking.id}")
        
        # Calculate totals
        booking.calculate_totals()
        booking.save()
        print(f"Booking total: {booking.total_amount_usd}")
        print(f"Total amount preferred: {booking.total_amount_preferred}")
        
        # Save passenger details
        passenger_count_saved = 0
        for passenger_form in form:
            if passenger_form.cleaned_data:
                print(f"Saving passenger: {passenger_form.cleaned_data}")
                passenger = passenger_form.save(commit=False)
                passenger.booking = booking
                passenger.save()
                passenger_count_saved += 1
        
        print(f"Saved {passenger_count_saved} passengers")
        
        # Clear session data
        if 'booking_data' in self.request.session:
            del self.request.session['booking_data']
        if 'selected_aircraft' in self.request.session:
            del self.request.session['selected_aircraft']
        
        messages.success(self.request, f'Booking {booking.booking_reference} created successfully!')
        print(f"Redirecting to: bookings:review with pk={booking.pk}")
        return redirect('bookings:review', pk=booking.pk)
    
    def form_invalid(self, form):
        print("=" * 50)
        print("FORM_INVALID CALLED - Form has errors!")
        print(f"Form errors: {form.errors}")
        
        # Print each form's errors
        for i, passenger_form in enumerate(form):
            if passenger_form.errors:
                print(f"Passenger {i+1} errors: {passenger_form.errors}")
        
        return self.render_to_response(self.get_context_data(form=form))
    

class BookingUpdateView(LoginRequiredMixin, UpdateView):
    model = Booking
    form_class = BookingForm
    template_name = 'bookings/booking_form.html'
    
    def get_queryset(self):
        return Booking.objects.filter(user=self.request.user, status='draft')
    
    def form_valid(self, form):
        form.instance.calculate_totals()
        messages.success(self.request, 'Booking updated successfully!')
        return super().form_valid(form)


class BookingCancelView(LoginRequiredMixin, UpdateView):
    model = Booking
    fields = []
    template_name = 'bookings/booking_cancel.html'
    
    def get_queryset(self):
        return Booking.objects.filter(user=self.request.user, status__in=['draft', 'confirmed'])
    
    def form_valid(self, form):
        self.object.cancel_booking(self.request.user, "Cancelled by user")
        messages.success(self.request, 'Booking cancelled successfully!')
        return redirect('bookings:list')


class InvoiceDetailView(LoginRequiredMixin, DetailView):
    model = Invoice
    template_name = 'bookings/invoice.html'
    context_object_name = 'invoice'
    
    def get_queryset(self):
        return Invoice.objects.filter(user=self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        booking = self.object.booking
        context['booking'] = booking
        
        # Add airport details for invoice display
        if booking.departure_airport:
            try:
                context['departure_airport'] = Airport.objects.get(iata_code=booking.departure_airport)
            except Airport.DoesNotExist:
                context['departure_airport'] = None
        
        if booking.arrival_airport:
            try:
                context['arrival_airport'] = Airport.objects.get(iata_code=booking.arrival_airport)
            except Airport.DoesNotExist:
                context['arrival_airport'] = None
        
        return context


class BookingTrackView(LoginRequiredMixin, ListView):
    """
    View for tracking a booking by reference.
    Requires login - redirects to login page if user is not authenticated.
    """
    model = Booking
    template_name = 'bookings/track.html'
    context_object_name = 'bookings'
    paginate_by = 10
    login_url = 'accounts:login'
    redirect_field_name = 'next'
    
    def get_queryset(self):
        query = self.request.GET.get('booking_reference', '')
        if query:
            return Booking.objects.filter(
                booking_reference__icontains=query,
                status__in=['confirmed', 'in_progress', 'paid'],
                user=self.request.user
            ).order_by('-departure_datetime')
        return Booking.objects.none()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('booking_reference', '')
        
        # Add airport details for tracked bookings
        bookings = context.get('bookings', [])
        for booking in bookings:
            if booking.departure_airport:
                try:
                    booking.departure_airport_obj = Airport.objects.get(iata_code=booking.departure_airport)
                except Airport.DoesNotExist:
                    booking.departure_airport_obj = None
            
            if booking.arrival_airport:
                try:
                    booking.arrival_airport_obj = Airport.objects.get(iata_code=booking.arrival_airport)
                except Airport.DoesNotExist:
                    booking.arrival_airport_obj = None
        
        return context
    
    def handle_no_permission(self):
        messages.info(self.request, 'Please log in or sign up to track your flights.')
        return redirect_to_login(
            self.request.get_full_path(),
            self.get_login_url(),
            self.get_redirect_field_name()
        )


def check_availability(request):
    """View to check aircraft availability based on search criteria with cargo support."""
    if request.method == 'GET':
        from_airport = request.GET.get('from', '')
        to_airport = request.GET.get('to', '')
        departure_date = request.GET.get('departure', '')
        passengers = request.GET.get('passengers', 1)
        
        try:
            passengers = int(passengers)
        except ValueError:
            passengers = 1
        
        # Get airport objects for display
        departure_airport_obj = None
        arrival_airport_obj = None
        
        if from_airport:
            try:
                departure_airport_obj = Airport.objects.get(iata_code=from_airport)
            except Airport.DoesNotExist:
                pass
        
        if to_airport:
            try:
                arrival_airport_obj = Airport.objects.get(iata_code=to_airport)
            except Airport.DoesNotExist:
                pass
        
        # Determine if this is a cargo search (0 passengers)
        is_cargo = passengers == 0
        
        if is_cargo:
            # For cargo: show cargo aircraft regardless of passenger capacity
            available_aircraft = Aircraft.objects.filter(
                is_active=True,
                status='available'
            ).filter(
                Q(category__category_type='cargo') | Q(cargo_capacity_kg__gt=0)
            ).distinct()
        else:
            # For passenger flights: filter by passenger capacity
            available_aircraft = Aircraft.objects.filter(
                is_active=True,
                status='available',
                passenger_capacity__gte=passengers
            )
        
        # Check availability for the date
        if departure_date:
            try:
                from datetime import datetime
                search_date = datetime.strptime(departure_date, '%Y-%m-%d').date()
                
                booked_aircraft = Booking.objects.filter(
                    Q(departure_datetime__date=search_date) |
                    Q(arrival_datetime__date=search_date),
                    status__in=['confirmed', 'paid', 'in_progress']
                ).values_list('aircraft_id', flat=True)
                
                available_aircraft = available_aircraft.exclude(id__in=booked_aircraft)
            except ValueError:
                pass
        
        context = {
            'aircraft': available_aircraft,
            'from_airport': from_airport,
            'to_airport': to_airport,
            'departure_airport': departure_airport_obj,
            'arrival_airport': arrival_airport_obj,
            'departure_date': departure_date,
            'passengers': passengers,
            'is_cargo': is_cargo,
            'search_performed': bool(from_airport and to_airport and departure_date)
        }
        
        return render(request, 'bookings/availability_results.html', context)
    
    return redirect('bookings:track')

class BookingReviewView(LoginRequiredMixin, DetailView):
    model = Booking
    template_name = 'bookings/booking_review.html'
    context_object_name = 'booking'
    
    def get_queryset(self):
        return Booking.objects.filter(user=self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        booking = context['booking']
        
        # Add airport details
        if booking.departure_airport:
            try:
                context['departure_airport'] = Airport.objects.get(iata_code=booking.departure_airport)
            except Airport.DoesNotExist:
                context['departure_airport'] = None
        
        if booking.arrival_airport:
            try:
                context['arrival_airport'] = Airport.objects.get(iata_code=booking.arrival_airport)
            except Airport.DoesNotExist:
                context['arrival_airport'] = None
        
        # ✅ ADD THIS - Get crypto wallets for debug display
        from apps.core.models import CryptoWallet
        context['crypto_wallets_debug'] = CryptoWallet.objects.filter(is_active=True)
        
        # Optional: Add debug print to see what's happening
        import sys
        print("\n" + "="*60, file=sys.stderr)
        print("📊 CRYPTO WALLETS IN VIEW:", file=sys.stderr)
        wallets = CryptoWallet.objects.filter(is_active=True)
        print(f"Total active wallets: {wallets.count()}", file=sys.stderr)
        for w in wallets:
            print(f"  - {w.crypto_type} ({w.network}): active={w.is_active}", file=sys.stderr)
            print(f"    Address: {w.wallet_address[:50]}...", file=sys.stderr)
        print("="*60 + "\n", file=sys.stderr)
        
        return context


class BookingHistoryView(LoginRequiredMixin, ListView):
    """
    View all booking history for the logged-in user.
    Shows all status changes for all user bookings.
    """
    model = BookingHistory
    template_name = 'bookings/booking_history.html'
    context_object_name = 'histories'
    paginate_by = 20
    
    def get_queryset(self):
        return BookingHistory.objects.filter(
            booking__user=self.request.user
        ).select_related('booking', 'changed_by').order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get all bookings for stats
        bookings = Booking.objects.filter(user=self.request.user)
        context['total_bookings'] = bookings.count()
        context['completed_bookings'] = bookings.filter(status='completed').count()
        context['upcoming_bookings'] = bookings.filter(
            departure_datetime__gte=timezone.now(),
            status__in=['confirmed', 'paid', 'in_progress']
        ).count()
        context['cancelled_bookings'] = bookings.filter(status='cancelled').count()
        
        # Group histories by booking for better display
        history_by_booking = {}
        for history in context['histories']:
            ref = history.booking.booking_reference
            if ref not in history_by_booking:
                history_by_booking[ref] = {
                    'booking': history.booking,
                    'histories': []
                }
                # Add airport objects to the booking
                booking = history_by_booking[ref]['booking']
                if booking.departure_airport:
                    try:
                        booking.departure_airport_obj = Airport.objects.get(iata_code=booking.departure_airport)
                    except Airport.DoesNotExist:
                        booking.departure_airport_obj = None
                
                if booking.arrival_airport:
                    try:
                        booking.arrival_airport_obj = Airport.objects.get(iata_code=booking.arrival_airport)
                    except Airport.DoesNotExist:
                        booking.arrival_airport_obj = None
            
            history_by_booking[ref]['histories'].append(history)
        
        context['history_by_booking'] = history_by_booking
        
        return context