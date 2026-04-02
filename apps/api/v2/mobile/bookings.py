from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.utils import timezone
from apps.bookings.models import Booking
from apps.bookings.serializers import BookingSerializer
import logging

logger = logging.getLogger(__name__)


@api_view(['GET'])
def mobile_bookings(request):
    """Get user's bookings (mobile optimized)"""
    # Get query parameters
    status_filter = request.query_params.get('status', '')
    page = int(request.query_params.get('page', 1))
    page_size = int(request.query_params.get('page_size', 20))
    
    # Filter bookings
    bookings = Booking.objects.filter(user=request.user)
    
    if status_filter:
        bookings = bookings.filter(status=status_filter)
    
    bookings = bookings.order_by('-created_at')
    
    # Pagination
    start = (page - 1) * page_size
    end = start + page_size
    
    total = bookings.count()
    results = bookings[start:end]
    
    serializer = BookingSerializer(results, many=True)
    
    return Response({
        'count': total,
        'next': page * page_size < total,
        'previous': page > 1,
        'results': serializer.data
    })


@api_view(['GET'])
def mobile_booking_detail(request, booking_id):
    """Get booking details (mobile optimized)"""
    try:
        booking = Booking.objects.get(id=booking_id, user=request.user)
    except Booking.DoesNotExist:
        return Response({
            'error': 'Booking not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    serializer = BookingSerializer(booking)
    data = serializer.data
    
    # Add additional mobile-specific fields
    data['share_url'] = f"/tracking/{booking.id}/" if booking.status == 'confirmed' else None
    data['can_cancel'] = booking.status in ['draft', 'confirmed'] and booking.departure_datetime > timezone.now()
    
    return Response(data)


@api_view(['POST'])
def mobile_create_booking(request):
    """Create booking (mobile optimized)"""
    # Simplified booking creation for mobile
    serializer = BookingSerializer(data=request.data)
    
    if serializer.is_valid():
        serializer.save(user=request.user, status='draft')
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
def mobile_cancel_booking(request, booking_id):
    """Cancel booking"""
    try:
        booking = Booking.objects.get(id=booking_id, user=request.user)
    except Booking.DoesNotExist:
        return Response({
            'error': 'Booking not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    if booking.status not in ['draft', 'pending', 'confirmed']:
        return Response({
            'error': 'Booking cannot be cancelled'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    if booking.departure_datetime <= timezone.now():
        return Response({
            'error': 'Cannot cancel a flight that has already departed'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    booking.status = 'cancelled'
    booking.save()
    
    return Response({'status': 'cancelled', 'booking_reference': booking.booking_reference})