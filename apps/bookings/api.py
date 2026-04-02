from rest_framework import viewsets, status, generics, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Q
from .models import Booking, BookingPassenger, BookingAddon, Invoice, InvoiceItem
from .serializers import (
    BookingSerializer, BookingCreateSerializer, BookingDetailSerializer,
    BookingPassengerSerializer, BookingAddonSerializer,
    InvoiceSerializer, InvoiceCreateSerializer
)
from .permissions import IsBookingOwnerOrReadOnly
from apps.fleet.models import Aircraft
from apps.fleet.serializers import AircraftListSerializer
from apps.payments.models import Payment
from apps.airports.models import Airport  # Add this import
import logging

logger = logging.getLogger(__name__)

class BookingViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Booking operations.
    """
    queryset = Booking.objects.all().order_by('-created_at')
    permission_classes = [permissions.IsAuthenticated, IsBookingOwnerOrReadOnly]
    
    def get_serializer_class(self):
        """Return different serializers for different actions."""
        if self.action == 'create':
            return BookingCreateSerializer
        elif self.action in ['retrieve', 'update', 'partial_update']:
            return BookingDetailSerializer
        return BookingSerializer
    
    def get_queryset(self):
        """Filter queryset based on user permissions."""
        user = self.request.user
        
        # Admin can see all bookings
        if user.is_staff or user.user_type == 'admin':
            return Booking.objects.all()
        
        # Agents can see bookings they manage
        if user.user_type == 'agent':
            return Booking.objects.filter(
                Q(user=user) | Q(assigned_agent=user)
            ).distinct()
        
        # Regular users can only see their own bookings
        return Booking.objects.filter(user=user)
    
    def perform_create(self, serializer):
        """Set the user when creating a booking."""
        serializer.save(user=self.request.user)
    
    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        """Confirm a booking."""
        booking = self.get_object()
        
        if booking.status != 'draft':
            return Response(
                {'error': f'Cannot confirm booking with status {booking.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        booking.confirm_booking(request.user)
        
        serializer = self.get_serializer(booking)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel a booking."""
        booking = self.get_object()
        reason = request.data.get('reason', '')
        
        if booking.status in ['completed', 'cancelled']:
            return Response(
                {'error': f'Cannot cancel booking with status {booking.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        booking.cancel_booking(request.user, reason)
        
        serializer = self.get_serializer(booking)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def invoice(self, request, pk=None):
        """Get invoice for booking."""
        booking = self.get_object()
        invoice = booking.invoices.first()
        
        if not invoice:
            return Response(
                {'error': 'No invoice found for this booking'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = InvoiceSerializer(invoice, context={'request': request})
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def payments(self, request, pk=None):
        """Get payments for booking."""
        booking = self.get_object()
        payments = booking.payments.all()
        
        from apps.payments.serializers import PaymentSerializer
        serializer = PaymentSerializer(payments, many=True, context={'request': request})
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def passengers(self, request, pk=None):
        """Get passengers for booking."""
        booking = self.get_object()
        passengers = booking.passenger_details.all()
        
        serializer = BookingPassengerSerializer(passengers, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def add_passenger(self, request, pk=None):
        """Add a passenger to booking."""
        booking = self.get_object()
        
        serializer = BookingPassengerSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(booking=booking)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def add_addon(self, request, pk=None):
        """Add an addon to booking."""
        booking = self.get_object()
        
        serializer = BookingAddonSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(booking=booking)
            
            # Recalculate booking total
            booking.calculate_totals()
            booking.save()
            
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def upcoming(self, request):
        """Get upcoming bookings for current user."""
        bookings = self.get_queryset().filter(
            departure_datetime__gte=timezone.now(),
            status__in=['confirmed', 'paid']
        ).order_by('departure_datetime')[:10]
        
        serializer = self.get_serializer(bookings, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def past(self, request):
        """Get past bookings for current user."""
        bookings = self.get_queryset().filter(
            departure_datetime__lt=timezone.now(),
            status='completed'
        ).order_by('-departure_datetime')[:10]
        
        serializer = self.get_serializer(bookings, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get booking statistics for current user."""
        user = request.user
        bookings = self.get_queryset()
        
        stats = {
            'total_bookings': bookings.count(),
            'confirmed_bookings': bookings.filter(status='confirmed').count(),
            'completed_bookings': bookings.filter(status='completed').count(),
            'cancelled_bookings': bookings.filter(status='cancelled').count(),
            'total_spent': sum(b.total_amount_usd for b in bookings.filter(status='completed')),
            'upcoming_flights': bookings.filter(
                departure_datetime__gte=timezone.now(),
                status__in=['confirmed', 'paid']
            ).count()
        }
        
        return Response(stats)


class InvoiceViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Invoice operations.
    """
    queryset = Invoice.objects.all().order_by('-invoice_date')
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return InvoiceCreateSerializer
        return InvoiceSerializer
    
    def get_queryset(self):
        """Filter queryset based on user permissions."""
        user = self.request.user
        
        if user.is_staff or user.user_type == 'admin':
            return Invoice.objects.all()
        
        return Invoice.objects.filter(user=user)
    
    def get_serializer_context(self):
        """Add request to serializer context."""
        context = super().get_serializer_context()
        context.update({'request': self.request})
        return context
    
    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        """Download invoice PDF."""
        try:
            # Fetch the invoice directly from the database
            invoice = Invoice.objects.get(id=pk, user=request.user)
            
            print(f"DEBUG: Invoice fetched successfully: {type(invoice)}")
            print(f"Invoice ID: {invoice.id}")
            print(f"Invoice number: {invoice.invoice_number}")
            
            # Generate PDF if not already generated
            if not invoice.pdf_file:
                from .utils import generate_invoice_pdf
                pdf_file = generate_invoice_pdf(invoice)
                if pdf_file:
                    invoice.pdf_file.save(f"invoice_{invoice.invoice_number}.pdf", pdf_file)
                    invoice.save()
            
            from django.http import FileResponse
            return FileResponse(invoice.pdf_file, as_attachment=True, filename=f"invoice_{invoice.invoice_number}.pdf")
            
        except Invoice.DoesNotExist:
            logger.error(f"Invoice not found with ID: {pk}")
            from django.http import HttpResponse
            return HttpResponse("Invoice not found", status=404)
        except Exception as e:
            logger.error(f"Error downloading invoice: {e}", exc_info=True)
            from django.http import HttpResponse
            return HttpResponse(f"Error generating document: {str(e)}", content_type='text/html')


class AvailableAircraftView(generics.ListAPIView):
    """
    API endpoint to get available aircraft for given dates.
    """
    serializer_class = AircraftListSerializer
    permission_classes = [permissions.AllowAny]
    
    def get_queryset(self):
        """Return available aircraft based on query parameters."""
        from django.db.models import Q
        
        departure = self.request.query_params.get('departure')
        arrival = self.request.query_params.get('arrival')
        date = self.request.query_params.get('date')
        passengers = self.request.query_params.get('passengers', 1)
        
        queryset = Aircraft.objects.filter(
            is_active=True,
            status='available',
            passenger_capacity__gte=passengers
        )
        
        # Check availability if date provided
        if date and departure and arrival:
            from datetime import datetime
            try:
                flight_date = datetime.strptime(date, '%Y-%m-%d')
                
                # Exclude aircraft already booked for this date
                booked_aircraft = Booking.objects.filter(
                    Q(departure_datetime__date=flight_date) |
                    Q(arrival_datetime__date=flight_date),
                    status__in=['confirmed', 'paid', 'in_progress']
                ).values_list('aircraft_id', flat=True)
                
                queryset = queryset.exclude(id__in=booked_aircraft)
            except ValueError:
                pass
        
        return queryset
    
    def list(self, request, *args, **kwargs):
        """Add airport details to response."""
        response = super().list(request, *args, **kwargs)
        
        # Add airport info for departure and arrival if provided
        departure = request.query_params.get('departure')
        arrival = request.query_params.get('arrival')
        
        airport_info = {}
        if departure:
            try:
                dep_airport = Airport.objects.get(iata_code=departure)
                airport_info['departure_airport'] = {
                    'iata_code': dep_airport.iata_code,
                    'name': dep_airport.name,
                    'city': dep_airport.city,
                    'country': dep_airport.country
                }
            except Airport.DoesNotExist:
                airport_info['departure_airport'] = {'iata_code': departure, 'name': None}
        
        if arrival:
            try:
                arr_airport = Airport.objects.get(iata_code=arrival)
                airport_info['arrival_airport'] = {
                    'iata_code': arr_airport.iata_code,
                    'name': arr_airport.name,
                    'city': arr_airport.city,
                    'country': arr_airport.country
                }
            except Airport.DoesNotExist:
                airport_info['arrival_airport'] = {'iata_code': arrival, 'name': None}
        
        if airport_info:
            response.data['airport_info'] = airport_info
        
        return response


class CheckAvailabilityView(generics.GenericAPIView):
    """
    API endpoint to check specific aircraft availability.
    """
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        aircraft_id = request.data.get('aircraft_id')
        start_datetime = request.data.get('start_datetime')
        end_datetime = request.data.get('end_datetime')
        
        try:
            aircraft = Aircraft.objects.get(id=aircraft_id)
            
            # Check if aircraft is available
            conflicting_bookings = Booking.objects.filter(
                aircraft=aircraft,
                status__in=['confirmed', 'paid', 'in_progress'],
                departure_datetime__lt=end_datetime,
                arrival_datetime__gt=start_datetime
            ).exists()
            
            is_available = not conflicting_bookings and aircraft.status == 'available'
            
            return Response({
                'is_available': is_available,
                'aircraft': AircraftListSerializer(aircraft).data
            })
            
        except Aircraft.DoesNotExist:
            return Response(
                {'error': 'Aircraft not found'},
                status=status.HTTP_404_NOT_FOUND
            )


class CalculatePriceView(generics.GenericAPIView):
    """
    API endpoint to calculate booking price.
    """
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        aircraft_id = request.data.get('aircraft_id')
        flight_hours = request.data.get('flight_hours', 1)
        passengers = request.data.get('passengers', 1)
        
        try:
            aircraft = Aircraft.objects.get(id=aircraft_id)
            
            # Calculate base price
            base_price = aircraft.hourly_rate_usd * float(flight_hours)
            
            # Add passenger charges
            passenger_charge = aircraft.catering_charge_per_pax * int(passengers)
            
            # Calculate total
            subtotal = base_price + passenger_charge
            tax = subtotal * 0.1  # 10% tax
            total = subtotal + tax
            
            return Response({
                'aircraft': aircraft.model,
                'flight_hours': flight_hours,
                'base_price': base_price,
                'passenger_charge': passenger_charge,
                'subtotal': subtotal,
                'tax': tax,
                'total': total,
                'currency': 'USD'
            })
            
        except Aircraft.DoesNotExist:
            return Response(
                {'error': 'Aircraft not found'},
                status=status.HTTP_404_NOT_FOUND
            )


class TrackBookingView(generics.RetrieveAPIView):
    """
    API endpoint to track a booking by reference.
    """
    serializer_class = BookingSerializer
    permission_classes = [permissions.AllowAny]
    lookup_field = 'booking_reference'
    lookup_url_kwarg = 'reference'
    
    def get_queryset(self):
        return Booking.objects.filter(status__in=['confirmed', 'paid', 'in_progress'])
    
    def retrieve(self, request, *args, **kwargs):
        try:
            booking = self.get_queryset().get(booking_reference=kwargs['reference'])
            serializer = self.get_serializer(booking)
            
            # Add airport details
            departure_airport_details = None
            arrival_airport_details = None
            
            if booking.departure_airport:
                try:
                    dep_airport = Airport.objects.get(iata_code=booking.departure_airport)
                    departure_airport_details = {
                        'iata_code': dep_airport.iata_code,
                        'name': dep_airport.name,
                        'city': dep_airport.city,
                        'country': dep_airport.country
                    }
                except Airport.DoesNotExist:
                    departure_airport_details = {'iata_code': booking.departure_airport}
            
            if booking.arrival_airport:
                try:
                    arr_airport = Airport.objects.get(iata_code=booking.arrival_airport)
                    arrival_airport_details = {
                        'iata_code': arr_airport.iata_code,
                        'name': arr_airport.name,
                        'city': arr_airport.city,
                        'country': arr_airport.country
                    }
                except Airport.DoesNotExist:
                    arrival_airport_details = {'iata_code': booking.arrival_airport}
            
            # Add tracking information
            data = serializer.data
            data['departure_airport_details'] = departure_airport_details
            data['arrival_airport_details'] = arrival_airport_details
            data['tracking'] = {
                'current_status': booking.status,
                'departure_time': booking.departure_datetime,
                'arrival_time': booking.arrival_datetime,
                'estimated_arrival': booking.arrival_datetime,
                'flight_progress': self.calculate_flight_progress(booking)
            }
            
            return Response(data)
            
        except Booking.DoesNotExist:
            return Response(
                {'error': 'Booking not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    def calculate_flight_progress(self, booking):
        """Calculate flight progress percentage."""
        now = timezone.now()
        
        if now < booking.departure_datetime:
            return 0
        elif now > booking.arrival_datetime:
            return 100
        else:
            total_duration = (booking.arrival_datetime - booking.departure_datetime).total_seconds()
            elapsed = (now - booking.departure_datetime).total_seconds()
            return int((elapsed / total_duration) * 100)


class MyBookingsView(generics.ListAPIView):
    """
    API endpoint for current user's bookings.
    """
    serializer_class = BookingSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        status_filter = self.request.query_params.get('status', None)
        
        queryset = Booking.objects.filter(user=user)
        
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        return queryset.order_by('-created_at')
    
    def list(self, request, *args, **kwargs):
        """Add airport details to each booking."""
        response = super().list(request, *args, **kwargs)
        
        # Add airport details to each booking
        for booking_data in response.data:
            if booking_data.get('departure_airport'):
                try:
                    airport = Airport.objects.get(iata_code=booking_data['departure_airport'])
                    booking_data['departure_airport_name'] = airport.name
                    booking_data['departure_airport_city'] = airport.city
                except Airport.DoesNotExist:
                    pass
            
            if booking_data.get('arrival_airport'):
                try:
                    airport = Airport.objects.get(iata_code=booking_data['arrival_airport'])
                    booking_data['arrival_airport_name'] = airport.name
                    booking_data['arrival_airport_city'] = airport.city
                except Airport.DoesNotExist:
                    pass
        
        return response


class RecentBookingsView(generics.ListAPIView):
    """
    API endpoint for recent bookings (admin only).
    """
    serializer_class = BookingSerializer
    permission_classes = [permissions.IsAdminUser]
    
    def get_queryset(self):
        return Booking.objects.all().order_by('-created_at')[:20]


class BookingStatsView(generics.GenericAPIView):
    """
    API endpoint for booking statistics (admin only).
    """
    permission_classes = [permissions.IsAdminUser]
    
    def get(self, request):
        from django.db.models import Count, Sum
        from django.db.models.functions import TruncMonth, TruncDay
        
        # Overall stats
        total_bookings = Booking.objects.count()
        total_revenue = Booking.objects.filter(status='completed').aggregate(Sum('total_amount_usd'))['total_amount_usd__sum'] or 0
        
        # Bookings by status
        status_counts = Booking.objects.values('status').annotate(count=Count('id'))
        
        # Bookings by month (last 12 months)
        monthly_bookings = Booking.objects.filter(
            created_at__gte=timezone.now() - timezone.timedelta(days=365)
        ).annotate(
            month=TruncMonth('created_at')
        ).values('month').annotate(
            count=Count('id'),
            revenue=Sum('total_amount_usd')
        ).order_by('month')
        
        # Popular routes with airport names
        popular_routes = Booking.objects.filter(
            status='completed'
        ).values(
            'departure_airport', 'arrival_airport'
        ).annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        # Add airport names to popular routes
        for route in popular_routes:
            if route['departure_airport']:
                try:
                    dep = Airport.objects.get(iata_code=route['departure_airport'])
                    route['departure_name'] = f"{dep.city} ({dep.iata_code})"
                except Airport.DoesNotExist:
                    route['departure_name'] = route['departure_airport']
            
            if route['arrival_airport']:
                try:
                    arr = Airport.objects.get(iata_code=route['arrival_airport'])
                    route['arrival_name'] = f"{arr.city} ({arr.iata_code})"
                except Airport.DoesNotExist:
                    route['arrival_name'] = route['arrival_airport']
        
        return Response({
            'total_bookings': total_bookings,
            'total_revenue': total_revenue,
            'status_breakdown': status_counts,
            'monthly_trend': monthly_bookings,
            'popular_routes': popular_routes
        })