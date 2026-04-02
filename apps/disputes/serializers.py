from rest_framework import serializers
from .models import Dispute, DisputeMessage, DisputeEvidence, DisputeResolution

class DisputeEvidenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = DisputeEvidence
        fields = ['id', 'evidence_type', 'file', 'description', 'uploaded_at']


class DisputeMessageSerializer(serializers.ModelSerializer):
    sender_name = serializers.CharField(source='sender.get_full_name', read_only=True)
    
    class Meta:
        model = DisputeMessage
        fields = ['id', 'sender', 'sender_name', 'message', 'attachment', 'created_at', 'is_staff', 'is_read']


class DisputeSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = Dispute
        fields = [
            'id', 'dispute_number', 'dispute_type', 'status', 'status_display',
            'priority', 'subject', 'disputed_amount', 'filed_at',
            'response_deadline', 'assigned_to'
        ]


class DisputeDetailSerializer(serializers.ModelSerializer):
    messages = DisputeMessageSerializer(many=True, read_only=True)
    evidence = DisputeEvidenceSerializer(many=True, read_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True)
    booking_reference = serializers.CharField(source='booking.booking_reference', read_only=True)
    
    class Meta:
        model = Dispute
        fields = '__all__'


class DisputeResolutionSerializer(serializers.ModelSerializer):
    class Meta:
        model = DisputeResolution
        fields = ['resolution_type', 'description', 'refund_amount', 'credit_amount']