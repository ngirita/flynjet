from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from .models import FlightTrack, TrackingShare, FlightAlert
from .serializers import (
    FlightTrackSerializer, FlightTrackDetailSerializer,
    TrackingShareSerializer, FlightAlertSerializer
)

class TrackingViewSet(viewsets.ModelViewSet):
    """API for flight tracking"""
    serializer_class = FlightTrackSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        if user.is_staff or user.user_type in ['admin', 'agent']:
            return FlightTrack.objects.all()
        return FlightTrack.objects.filter(booking__user=user)
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return FlightTrackDetailSerializer
        return FlightTrackSerializer
    
    @action(detail=True, methods=['post'])
    def share(self, request, pk=None):
        """Generate shareable link"""
        track = self.get_object()
        
        hours = int(request.data.get('hours', 24))
        password = request.data.get('password', '')
        
        share = TrackingShare.objects.create(
            track=track,
            created_by=request.user,
            expires_at=timezone.now() + timezone.timedelta(hours=hours),
            password=password
        )
        
        serializer = TrackingShareSerializer(share)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def positions(self, request, pk=None):
        """Get position history"""
        track = self.get_object()
        positions = track.position_history.all().order_by('-timestamp')[:100]
        
        data = [{
            'lat': p.latitude,
            'lng': p.longitude,
            'alt': p.altitude,
            'heading': p.heading,
            'speed': p.speed,
            'timestamp': p.timestamp.isoformat()
        } for p in positions]
        
        return Response(data)


class TrackingShareViewSet(viewsets.ReadOnlyModelViewSet):
    """API for shared tracking links"""
    serializer_class = TrackingShareSerializer
    permission_classes = [permissions.AllowAny]
    lookup_field = 'token'
    
    def get_queryset(self):
        return TrackingShare.objects.filter(expires_at__gt=timezone.now())
    
    @action(detail=True, methods=['post'])
    def verify_password(self, request, token=None):
        """Verify share password"""
        share = self.get_object()
        password = request.data.get('password', '')
        
        if share.check_password(password):
            return Response({'valid': True})
        return Response({'valid': False}, status=status.HTTP_401_UNAUTHORIZED)


class FlightAlertViewSet(viewsets.ModelViewSet):
    """API for flight alerts"""
    serializer_class = FlightAlertSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return FlightAlert.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)