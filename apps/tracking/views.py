import json
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView, ListView, DetailView
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.decorators import method_decorator
from django.conf import settings
from .models import FlightTrack, TrackingShare, FlightAlert
from apps.bookings.models import Booking


class TrackingDashboardView(LoginRequiredMixin, TemplateView):
    """Main tracking dashboard"""
    template_name = 'tracking/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Get active tracks
        if user.is_staff or getattr(user, 'user_type', '') in ['admin', 'agent']:
            tracks = FlightTrack.objects.all().order_by('-last_update')[:20]
        else:
            bookings = user.bookings.filter(status__in=['confirmed', 'in_progress'])
            tracks = FlightTrack.objects.filter(booking__in=bookings)
        
        # Organize tracks by status
        context['tracks'] = tracks
        context['active_tracks'] = tracks.filter(status__in=['departed', 'in_air', 'en_route', 'boarding'])
        context['scheduled_tracks'] = tracks.filter(status='scheduled')
        context['completed_tracks'] = tracks.filter(status='arrived')
        context['delayed_tracks'] = tracks.filter(status='delayed')
        
        # Cargo tracking
        context['cargo_tracks'] = tracks.exclude(cargo_status='delivered').exclude(cargo_status='')
        
        # No mapbox token needed for OpenStreetMap
        context['mapbox_token'] = ''
        return context


class CargoTrackingView(LoginRequiredMixin, TemplateView):
    """Cargo tracking dashboard"""
    template_name = 'tracking/cargo_tracking.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        if user.is_staff or getattr(user, 'user_type', '') in ['admin', 'agent']:
            tracks = FlightTrack.objects.exclude(cargo_manifest=[]).order_by('-last_update')
        else:
            bookings = user.bookings.filter(status__in=['confirmed', 'in_progress'])
            tracks = FlightTrack.objects.filter(booking__in=bookings).exclude(cargo_manifest=[])
        
        context['cargo_tracks'] = tracks
        context['mapbox_token'] = ''
        return context


def cargo_status_api(request, track_id):
    """API endpoint for cargo status"""
    try:
        track = FlightTrack.objects.get(id=track_id)
        data = {
            'flight_number': track.flight_number,
            'cargo_status': track.cargo_status,
            'cargo_status_display': track.get_cargo_status_display(),
            'cargo_manifest': track.cargo_manifest,
            'cargo_weight': track.cargo_weight,
            'status': track.status,
            'status_display': track.get_status_display(),
            'departure_airport': track.departure_airport,
            'arrival_airport': track.arrival_airport,
            'last_update': track.last_update.isoformat() if track.last_update else None,
            'remarks': track.remarks,
        }
        return JsonResponse(data)
    except FlightTrack.DoesNotExist:
        return JsonResponse({'error': 'Track not found'}, status=404)


class FlightTrackingView(LoginRequiredMixin, TemplateView):
    """Real-time flight tracking page"""
    template_name = 'tracking/flight_track.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        booking_id = self.kwargs.get('booking_id')
        
        # Get booking and track
        booking = get_object_or_404(Booking, id=booking_id)
        
        # Check permission
        user = self.request.user
        if not (user.is_staff or getattr(user, 'user_type', '') in ['admin', 'agent'] or user == booking.user):
            messages.error(self.request, "You don't have permission to view this flight")
            return redirect('tracking:dashboard')
        
        # Get or create track with all required fields
        track, created = FlightTrack.objects.get_or_create(
            booking=booking,
            defaults={
                'flight_number': f"FLT{booking.booking_reference}"[:20] if booking.booking_reference else f"FLT{booking.id}",
                'aircraft_registration': getattr(booking.aircraft, 'registration_number', 'N/A') if hasattr(booking, 'aircraft') and booking.aircraft else 'N/A',
                'departure_time': booking.departure_datetime,
                'arrival_time': booking.arrival_datetime,
                'departure_airport': booking.departure_airport,
                'arrival_airport': booking.arrival_airport,
                'status': 'scheduled',
                'cargo_status': 'pending',
                'data_source': 'manual',
            }
        )
        
        context['track'] = track
        context['booking'] = booking
        context['mapbox_token'] = ''  # OpenStreetMap doesn't need a token
        context['ws_url'] = f"ws://{self.request.get_host()}/ws/tracking/{booking_id}/"
        return context


class SharedTrackingView(TemplateView):
    """Public shared tracking page"""
    template_name = 'tracking/shared.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        token = self.kwargs.get('token')
        
        share = get_object_or_404(TrackingShare, token=token)
        
        if not share.is_valid():
            messages.error(self.request, "This tracking link has expired")
            return redirect('core:home')
        
        share.record_view()
        
        context['track'] = share.track
        context['share'] = share
        context['mapbox_token'] = ''
        context['ws_url'] = f"ws://{self.request.get_host()}/ws/tracking/share/{token}/"
        return context


class TrackingHistoryView(LoginRequiredMixin, TemplateView):
    """Flight tracking history"""
    template_name = 'tracking/history.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        booking_id = self.kwargs.get('booking_id')
        
        booking = get_object_or_404(Booking, id=booking_id)
        track = get_object_or_404(FlightTrack, booking=booking)
        
        positions = track.position_history.all().order_by('-timestamp')[:100]
        
        context['track'] = track
        context['booking'] = booking
        context['positions'] = positions
        context['mapbox_token'] = ''
        return context


@csrf_exempt
def update_position(request, track_id):
    """API endpoint to update aircraft position"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
        track = FlightTrack.objects.get(id=track_id)
        
        track.update_position(
            latitude=data.get('lat'),
            longitude=data.get('lng'),
            altitude=data.get('alt'),
            heading=data.get('heading'),
            speed=data.get('speed')
        )
        
        return JsonResponse({'status': 'success', 'track': str(track.id)})
    except FlightTrack.DoesNotExist:
        return JsonResponse({'error': 'Track not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)