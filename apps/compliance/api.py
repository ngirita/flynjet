from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from .models import ConsentRecord, DataSubjectRequest, BreachNotification
from .serializers import (
    ConsentRecordSerializer, DataSubjectRequestSerializer,
    BreachNotificationSerializer
)

class ConsentViewSet(viewsets.ModelViewSet):
    """API for managing user consent"""
    serializer_class = ConsentRecordSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return ConsentRecord.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        serializer.save(
            user=self.request.user,
            ip_address=self.request.META.get('REMOTE_ADDR'),
            user_agent=self.request.META.get('HTTP_USER_AGENT', '')
        )
    
    @action(detail=False, methods=['get'])
    def current(self, request):
        """Get current consent status for all types"""
        consents = {}
        for consent_type, _ in ConsentRecord.CONSENT_TYPES:
            latest = ConsentRecord.objects.filter(
                user=request.user,
                consent_type=consent_type
            ).order_by('-created_at').first()
            
            consents[consent_type] = {
                'granted': latest.granted if latest else False,
                'version': latest.version if latest else '1.0',
                'date': latest.created_at if latest else None
            }
        
        return Response(consents)


class DataSubjectRequestViewSet(viewsets.ModelViewSet):
    """API for data subject requests"""
    serializer_class = DataSubjectRequestSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return DataSubjectRequest.objects.all()
        return DataSubjectRequest.objects.filter(user=user)
    
    def perform_create(self, serializer):
        serializer.save(
            user=self.request.user,
            requester_name=self.request.user.get_full_name() or self.request.user.email,
            requester_email=self.request.user.email
        )
    
    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAdminUser])
    def process(self, request, pk=None):
        """Start processing a request (admin only)"""
        dsr = self.get_object()
        dsr.process(request.user)
        return Response({'status': 'processing'})
    
    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAdminUser])
    def complete(self, request, pk=None):
        """Complete a request (admin only)"""
        dsr = self.get_object()
        dsr.complete()
        return Response({'status': 'completed'})


class BreachNotificationViewSet(viewsets.ModelViewSet):
    """API for breach notifications (admin only)"""
    serializer_class = BreachNotificationSerializer
    permission_classes = [permissions.IsAdminUser]
    queryset = BreachNotification.objects.all().order_by('-detected_at')
    
    @action(detail=True, methods=['post'])
    def notify_authorities(self, request, pk=None):
        """Notify authorities of breach"""
        breach = self.get_object()
        breach.notify_authorities()
        return Response({'status': 'notified'})
    
    @action(detail=True, methods=['post'])
    def notify_users(self, request, pk=None):
        """Notify affected users"""
        breach = self.get_object()
        breach.notify_affected_users()
        return Response({'status': 'notified'})