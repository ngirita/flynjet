from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Dispute, DisputeMessage, DisputeResolution
from .serializers import (
    DisputeSerializer, DisputeDetailSerializer,
    DisputeMessageSerializer, DisputeResolutionSerializer
)

class DisputeViewSet(viewsets.ModelViewSet):
    """API for disputes"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        if user.is_staff or user.user_type in ['admin', 'agent']:
            return Dispute.objects.all()
        return Dispute.objects.filter(user=user)
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return DisputeDetailSerializer
        return DisputeSerializer
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
    
    @action(detail=True, methods=['post'])
    def add_message(self, request, pk=None):
        """Add message to dispute"""
        dispute = self.get_object()
        
        serializer = DisputeMessageSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(
                dispute=dispute,
                sender=request.user,
                is_staff=request.user.is_staff
            )
            return Response(serializer.data)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAdminUser])
    def assign(self, request, pk=None):
        """Assign dispute to agent"""
        dispute = self.get_object()
        agent_id = request.data.get('agent_id')
        
        from apps.accounts.models import User
        try:
            agent = User.objects.get(id=agent_id)
            dispute.assign_to(agent)
            return Response({'status': 'assigned'})
        except User.DoesNotExist:
            return Response({'error': 'Agent not found'}, status=404)
    
    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAdminUser])
    def resolve(self, request, pk=None):
        """Resolve dispute"""
        dispute = self.get_object()
        
        serializer = DisputeResolutionSerializer(data=request.data)
        if serializer.is_valid():
            resolution = serializer.save(
                dispute=dispute,
                proposed_by=request.user
            )
            
            dispute.resolve(
                resolution=resolution.description,
                outcome=f"Resolved with {resolution.get_resolution_type_display()}",
                resolved_by=request.user,
                refund_amount=resolution.refund_amount
            )
            
            return Response(serializer.data)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class DisputeMessageViewSet(viewsets.ModelViewSet):
    """API for dispute messages"""
    serializer_class = DisputeMessageSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return DisputeMessage.objects.filter(dispute__user=self.request.user)


class DisputeResolutionViewSet(viewsets.ReadOnlyModelViewSet):
    """API for dispute resolutions"""
    serializer_class = DisputeResolutionSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return DisputeResolution.objects.filter(dispute__user=self.request.user)