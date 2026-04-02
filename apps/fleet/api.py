from rest_framework import viewsets, status, generics, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Q, Count, Avg
from .models import (
    Aircraft, AircraftCategory, AircraftManufacturer,
    AircraftImage, AircraftSpecification, AircraftAvailability,
    AircraftMaintenance, AircraftDocument, FleetStats
)
from .serializers import (
    AircraftSerializer, AircraftListSerializer, AircraftDetailSerializer,
    AircraftCategorySerializer, AircraftManufacturerSerializer,
    AircraftImageSerializer, AircraftSpecificationSerializer,
    AircraftAvailabilitySerializer, AircraftMaintenanceSerializer,
    AircraftMaintenanceCreateSerializer, AircraftDocumentSerializer,
    FleetStatsSerializer
)
from .permissions import IsAdminOrReadOnly, IsMaintenanceTeamOrReadOnly
from apps.bookings.models import Booking
import logging

logger = logging.getLogger(__name__)


class AircraftViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Aircraft operations.
    """
    queryset = Aircraft.objects.all().order_by('manufacturer__name', 'model')
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsAdminOrReadOnly]
    
    def get_serializer_class(self):
        """Return different serializers for different actions."""
        if self.action == 'list':
            return AircraftListSerializer
        elif self.action == 'retrieve':
            return AircraftDetailSerializer
        return AircraftSerializer
    
    def get_queryset(self):
        """Filter queryset based on query parameters."""
        queryset = Aircraft.objects.all()
        
        # Filter by status
        status = self.request.query_params.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        # Filter by category
        category = self.request.query_params.get('category')
        if category:
            queryset = queryset.filter(category__slug=category)
        
        # Filter by manufacturer
        manufacturer = self.request.query_params.get('manufacturer')
        if manufacturer:
            queryset = queryset.filter(manufacturer__slug=manufacturer)
        
        # Filter by passenger capacity
        min_passengers = self.request.query_params.get('min_passengers')
        if min_passengers:
            queryset = queryset.filter(passenger_capacity__gte=min_passengers)
        
        # Filter by range
        min_range = self.request.query_params.get('min_range')
        if min_range:
            queryset = queryset.filter(max_range_nm__gte=min_range)
        
        # Filter by price range
        max_price = self.request.query_params.get('max_price')
        if max_price:
            queryset = queryset.filter(hourly_rate_usd__lte=max_price)
        
        # Search by model or registration
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(model__icontains=search) |
                Q(registration_number__icontains=search) |
                Q(manufacturer__name__icontains=search)
            )
        
        # Only show active aircraft to non-staff
        if not self.request.user.is_staff:
            queryset = queryset.filter(is_active=True)
        
        return queryset.distinct()
    
    @action(detail=False, methods=['get'])
    def available(self, request):
        """Get available aircraft for given dates."""
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        passengers = request.query_params.get('passengers', 1)
        
        queryset = self.get_queryset().filter(
            status='available',
            is_active=True,
            passenger_capacity__gte=passengers
        )
        
        if start_date and end_date:
            # Exclude aircraft already booked for these dates
            from datetime import datetime
            try:
                start = datetime.fromisoformat(start_date)
                end = datetime.fromisoformat(end_date)
                
                booked_aircraft = Booking.objects.filter(
                    Q(departure_datetime__lt=end, arrival_datetime__gt=start),
                    status__in=['confirmed', 'paid', 'in_progress']
                ).values_list('aircraft_id', flat=True)
                
                queryset = queryset.exclude(id__in=booked_aircraft)
            except ValueError:
                pass
        
        serializer = AircraftListSerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def availability(self, request, pk=None):
        """Get availability for a specific aircraft."""
        aircraft = self.get_object()
        
        # Get date range from query params
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        months = int(request.query_params.get('months', 3))
        
        from datetime import datetime, timedelta
        
        if not start_date:
            start_date = timezone.now().date()
        else:
            start_date = datetime.fromisoformat(start_date).date()
        
        if not end_date:
            end_date = start_date + timedelta(days=30 * months)
        else:
            end_date = datetime.fromisoformat(end_date).date()
        
        # Get existing bookings
        bookings = Booking.objects.filter(
            aircraft=aircraft,
            status__in=['confirmed', 'paid', 'in_progress'],
            departure_datetime__date__gte=start_date,
            departure_datetime__date__lte=end_date
        ).order_by('departure_datetime')
        
        # Get maintenance schedules
        maintenance = AircraftMaintenance.objects.filter(
            aircraft=aircraft,
            status__in=['scheduled', 'in_progress'],
            scheduled_start__date__gte=start_date,
            scheduled_start__date__lte=end_date
        ).order_by('scheduled_start')
        
        # Generate availability calendar
        calendar = []
        current_date = start_date
        
        while current_date <= end_date:
            day_status = {
                'date': current_date.isoformat(),
                'available': True,
                'bookings': [],
                'maintenance': []
            }
            
            # Check bookings for this day
            for booking in bookings:
                if booking.departure_datetime.date() <= current_date <= booking.arrival_datetime.date():
                    day_status['available'] = False
                    day_status['bookings'].append({
                        'id': str(booking.id),
                        'reference': booking.booking_reference,
                        'start': booking.departure_datetime.isoformat(),
                        'end': booking.arrival_datetime.isoformat()
                    })
            
            # Check maintenance for this day
            for maint in maintenance:
                if maint.scheduled_start.date() <= current_date <= maint.scheduled_end.date():
                    day_status['available'] = False
                    day_status['maintenance'].append({
                        'id': str(maint.id),
                        'title': maint.title,
                        'type': maint.maintenance_type,
                        'start': maint.scheduled_start.isoformat(),
                        'end': maint.scheduled_end.isoformat()
                    })
            
            calendar.append(day_status)
            current_date += timedelta(days=1)
        
        return Response({
            'aircraft_id': str(aircraft.id),
            'registration': aircraft.registration_number,
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'calendar': calendar
        })
    
    @action(detail=True, methods=['get'])
    def specifications(self, request, pk=None):
        """Get specifications for an aircraft."""
        aircraft = self.get_object()
        specs = aircraft.specifications.all()
        serializer = AircraftSpecificationSerializer(specs, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def images(self, request, pk=None):
        """Get images for an aircraft."""
        aircraft = self.get_object()
        images = aircraft.images.all().order_by('sort_order')
        serializer = AircraftImageSerializer(images, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def add_image(self, request, pk=None):
        """Add an image to aircraft (admin only)."""
        aircraft = self.get_object()
        
        if not request.user.is_staff:
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = AircraftImageSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(aircraft=aircraft)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def update_status(self, request, pk=None):
        """Update aircraft status (admin/maintenance only)."""
        aircraft = self.get_object()
        new_status = request.data.get('status')
        reason = request.data.get('reason', '')
        
        if new_status not in dict(Aircraft.AIRCRAFT_STATUS):
            return Response(
                {'error': 'Invalid status'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        aircraft.update_status(new_status)
        
        # Log the change
        from apps.core.models import ActivityLog
        ActivityLog.objects.create(
            user=request.user,
            activity_type='status_change',
            description=f'Aircraft {aircraft.registration_number} status changed to {new_status}: {reason}',
            related_object=aircraft
        )
        
        return Response({'message': f'Status updated to {new_status}'})
    
    @action(detail=True, methods=['get'])
    def maintenance_history(self, request, pk=None):
        """Get maintenance history for aircraft."""
        aircraft = self.get_object()
        maintenance = aircraft.maintenance_records.all().order_by('-scheduled_start')
        
        page = self.paginate_queryset(maintenance)
        if page is not None:
            serializer = AircraftMaintenanceSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = AircraftMaintenanceSerializer(maintenance, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def documents(self, request, pk=None):
        """Get documents for aircraft."""
        aircraft = self.get_object()
        documents = aircraft.documents.all().order_by('-issue_date')
        
        serializer = AircraftDocumentSerializer(documents, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def featured(self, request):
        """Get featured aircraft."""
        featured = self.get_queryset().filter(is_featured=True)[:6]
        serializer = AircraftListSerializer(featured, many=True, context={'request': request})
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get fleet statistics (admin only)."""
        if not request.user.is_staff:
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        total = Aircraft.objects.count()
        available = Aircraft.objects.filter(status='available').count()
        maintenance = Aircraft.objects.filter(status='maintenance').count()
        booked = Aircraft.objects.filter(status='booked').count()
        
        # Average utilization
        thirty_days_ago = timezone.now() - timezone.timedelta(days=30)
        bookings_last_30_days = Booking.objects.filter(
            departure_datetime__gte=thirty_days_ago,
            status='completed'
        ).count()
        
        utilization_rate = (bookings_last_30_days / (total * 30)) * 100 if total > 0 else 0
        
        # Category breakdown
        categories = AircraftCategory.objects.annotate(
            aircraft_count=Count('aircraft')
        ).values('name', 'aircraft_count')
        
        return Response({
            'total_aircraft': total,
            'available': available,
            'in_maintenance': maintenance,
            'booked': booked,
            'utilization_rate': round(utilization_rate, 2),
            'categories': categories
        })


class AircraftCategoryViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Aircraft Categories.
    """
    queryset = AircraftCategory.objects.all().order_by('sort_order', 'name')
    serializer_class = AircraftCategorySerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsAdminOrReadOnly]
    lookup_field = 'slug'
    
    @action(detail=True, methods=['get'])
    def aircraft(self, request, slug=None):
        """Get aircraft in this category."""
        category = self.get_object()
        aircraft = Aircraft.objects.filter(category=category, is_active=True)
        
        serializer = AircraftListSerializer(aircraft, many=True, context={'request': request})
        return Response(serializer.data)


class AircraftManufacturerViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Aircraft Manufacturers.
    """
    queryset = AircraftManufacturer.objects.all().order_by('name')
    serializer_class = AircraftManufacturerSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsAdminOrReadOnly]
    lookup_field = 'slug'
    
    @action(detail=True, methods=['get'])
    def aircraft(self, request, slug=None):
        """Get aircraft from this manufacturer."""
        manufacturer = self.get_object()
        aircraft = Aircraft.objects.filter(manufacturer=manufacturer, is_active=True)
        
        serializer = AircraftListSerializer(aircraft, many=True, context={'request': request})
        return Response(serializer.data)


class AircraftMaintenanceViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Aircraft Maintenance records.
    """
    permission_classes = [permissions.IsAuthenticated, IsMaintenanceTeamOrReadOnly]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return AircraftMaintenanceCreateSerializer
        return AircraftMaintenanceSerializer
    
    def get_queryset(self):
        """Filter by aircraft if specified."""
        queryset = AircraftMaintenance.objects.all().order_by('-scheduled_start')
        
        aircraft_id = self.request.query_params.get('aircraft')
        if aircraft_id:
            queryset = queryset.filter(aircraft_id=aircraft_id)
        
        status = self.request.query_params.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        return queryset
    
    def perform_create(self, serializer):
        """Set created_by when creating maintenance record."""
        serializer.save(created_by=self.request.user)
    
    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        """Start maintenance."""
        maintenance = self.get_object()
        maintenance.start_maintenance()
        return Response({'message': 'Maintenance started'})
    
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """Complete maintenance."""
        maintenance = self.get_object()
        actual_cost = request.data.get('actual_cost')
        maintenance.complete_maintenance(actual_cost)
        return Response({'message': 'Maintenance completed'})
    
    @action(detail=True, methods=['post'])
    def add_part(self, request, pk=None):
        """Add part used in maintenance."""
        maintenance = self.get_object()
        part_data = request.data
        
        parts = maintenance.parts_used or []
        parts.append(part_data)
        maintenance.parts_used = parts
        maintenance.save()
        
        return Response({'message': 'Part added'})


class AircraftDocumentViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Aircraft Documents.
    """
    serializer_class = AircraftDocumentSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminOrReadOnly]
    
    def get_queryset(self):
        queryset = AircraftDocument.objects.all().order_by('-issue_date')
        
        aircraft_id = self.request.query_params.get('aircraft')
        if aircraft_id:
            queryset = queryset.filter(aircraft_id=aircraft_id)
        
        # Filter by expiry
        expiring_soon = self.request.query_params.get('expiring_soon')
        if expiring_soon:
            thirty_days = timezone.now().date() + timezone.timedelta(days=30)
            queryset = queryset.filter(
                expiry_date__lte=thirty_days,
                expiry_date__gte=timezone.now().date()
            )
        
        return queryset
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve document."""
        document = self.get_object()
        document.is_approved = True
        document.approved_by = request.user
        document.approved_at = timezone.now()
        document.save()
        
        return Response({'message': 'Document approved'})


class FleetStatsViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for Fleet Statistics.
    """
    serializer_class = FleetStatsSerializer
    permission_classes = [permissions.IsAdminUser]
    
    def get_queryset(self):
        queryset = FleetStats.objects.all().order_by('-date')
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        
        if start_date:
            queryset = queryset.filter(date__gte=start_date)
        if end_date:
            queryset = queryset.filter(date__lte=end_date)
        
        return queryset
    
    @action(detail=False, methods=['get'])
    def latest(self, request):
        """Get latest fleet statistics."""
        latest = FleetStats.objects.order_by('-date').first()
        
        if latest:
            serializer = self.get_serializer(latest)
            return Response(serializer.data)
        
        return Response({'message': 'No statistics available'})


class FleetDashboardView(generics.GenericAPIView):
    """
    Dashboard data for fleet management.
    """
    permission_classes = [permissions.IsAdminUser]
    
    def get(self, request):
        # Current status
        total = Aircraft.objects.count()
        available = Aircraft.objects.filter(status='available').count()
        maintenance = Aircraft.objects.filter(status='maintenance').count()
        booked = Aircraft.objects.filter(status='booked').count()
        
        # Upcoming maintenance
        thirty_days = timezone.now() + timezone.timedelta(days=30)
        upcoming_maintenance = AircraftMaintenance.objects.filter(
            scheduled_start__lte=thirty_days,
            scheduled_start__gte=timezone.now(),
            status='scheduled'
        ).order_by('scheduled_start')[:10]
        
        # Documents expiring soon
        sixty_days = timezone.now().date() + timezone.timedelta(days=60)
        expiring_docs = AircraftDocument.objects.filter(
            expiry_date__lte=sixty_days,
            expiry_date__gte=timezone.now().date(),
            is_approved=True
        ).select_related('aircraft')[:10]
        
        # Recent activity
        from apps.core.models import ActivityLog
        recent_activity = ActivityLog.objects.filter(
            activity_type__in=['status_change', 'maintenance', 'document_upload']
        ).order_by('-timestamp')[:20]
        
        return Response({
            'aircraft_status': {
                'total': total,
                'available': available,
                'maintenance': maintenance,
                'booked': booked,
                'available_percentage': round((available / total) * 100 if total > 0 else 0, 2)
            },
            'upcoming_maintenance': AircraftMaintenanceSerializer(upcoming_maintenance, many=True).data,
            'expiring_documents': AircraftDocumentSerializer(expiring_docs, many=True).data,
            'recent_activity': [
                {
                    'id': str(log.id),
                    'type': log.activity_type,
                    'description': log.description,
                    'timestamp': log.timestamp,
                    'user': log.user.email if log.user else 'System'
                }
                for log in recent_activity
            ]
        })