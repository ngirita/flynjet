from rest_framework import serializers
from django.utils import timezone
from .models import ConsentRecord, DataProcessingAgreement, DataSubjectRequest, BreachNotification

class ConsentRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConsentRecord
        fields = ['id', 'consent_type', 'version', 'granted', 'created_at', 'withdrawn_at']
        read_only_fields = ['id', 'created_at', 'withdrawn_at']


class DataProcessingAgreementSerializer(serializers.ModelSerializer):
    class Meta:
        model = DataProcessingAgreement
        fields = '__all__'
        read_only_fields = ['agreement_number', 'created_at', 'updated_at']


class DataSubjectRequestSerializer(serializers.ModelSerializer):
    days_remaining = serializers.SerializerMethodField()
    
    class Meta:
        model = DataSubjectRequest
        fields = [
            'id', 'request_number', 'request_type', 'status',
            'description', 'submitted_at', 'deadline', 'completed_at',
            'days_remaining', 'response_file', 'response_notes'
        ]
        read_only_fields = [
            'request_number', 'submitted_at', 'deadline',
            'completed_at', 'days_remaining'
        ]
    
    def get_days_remaining(self, obj):
        if obj.deadline and obj.status not in ['completed', 'rejected']:
            delta = obj.deadline - timezone.now()
            return delta.days
        return None


class BreachNotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = BreachNotification
        fields = '__all__'
        read_only_fields = ['breach_number', 'detected_at']