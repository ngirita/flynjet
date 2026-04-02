from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from apps.tracking.models import FlightTrack
from apps.bookings.models import Booking
import logging

logger = logging.getLogger(__name__)


@api_view(['GET'])
def mobile_track_flight(request, booking_id):
    """Get flight tracking data (mobile optimized)"""
    try:
        booking = Booking.objects.get(id=booking_id, user=request.user)
        track = FlightTrack.objects.get(booking=booking)
    except Booking.DoesNotExist:
        return Response({
            'error': 'Booking not found'
        }, status=404)
    except FlightTrack.DoesNotExist:
        return Response({
            'error': 'Tracking not available for this booking'
        }, status=404)
    
    data = {
        'booking_reference': booking.booking_reference,
        'flight_number': track.flight_number,
        'aircraft': track.aircraft_registration,
        'position': {
            'lat': track.latitude,
            'lng': track.longitude,
            'altitude': track.altitude,
            'speed': track.speed,
            'heading': track.heading
        } if track.latitude else None,
        'progress': track.progress_percentage,
        'departure': {
            'airport': track.departure_airport,
            'time': track.departure_time.isoformat() if track.departure_time else None
        },
        'arrival': {
            'airport': track.arrival_airport,
            'estimated': track.estimated_arrival.isoformat() if track.estimated_arrival else None,
            'scheduled': track.arrival_time.isoformat() if track.arrival_time else None
        },
        'status': booking.status,
        'last_update': track.last_update.isoformat() if track.last_update else None
    }
    
    return Response(data)


@api_view(['GET'])
def mobile_track_history(request, booking_id):
    """Get tracking history"""
    try:
        booking = Booking.objects.get(id=booking_id, user=request.user)
        track = FlightTrack.objects.get(booking=booking)
    except (Booking.DoesNotExist, FlightTrack.DoesNotExist):
        return Response({
            'error': 'Tracking not available'
        }, status=404)
    
    positions = track.position_history.all().order_by('-timestamp')[:100]
    
    data = [{
        'lat': p.latitude,
        'lng': p.longitude,
        'alt': p.altitude,
        'speed': p.speed,
        'timestamp': p.timestamp.isoformat()
    } for p in positions]
    
    return Response(data)


@api_view(['POST'])
def mobile_share_tracking(request, booking_id):
    """Generate shareable tracking link"""
    try:
        booking = Booking.objects.get(id=booking_id, user=request.user)
        track = FlightTrack.objects.get(booking=booking)
    except (Booking.DoesNotExist, FlightTrack.DoesNotExist):
        return Response({
            'error': 'Tracking not available'
        }, status=404)
    
    hours = int(request.data.get('hours', 24))
    password = request.data.get('password', '')
    
    share = track.generate_share_token(hours)
    if password:
        share.password = password
        share.save()
    
    return Response({
        'share_token': str(share),
        'share_url': f"/tracking/share/{share}/",
        'expires_at': track.share_expiry.isoformat() if track.share_expiry else None
    })