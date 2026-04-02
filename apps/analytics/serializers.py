from rest_framework import serializers
from .models import AnalyticsEvent, DailyMetric, Report, Dashboard

class AnalyticsEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnalyticsEvent
        fields = '__all__'
        read_only_fields = ['event_id', 'timestamp']

class DailyMetricSerializer(serializers.ModelSerializer):
    class Meta:
        model = DailyMetric
        fields = '__all__'

class ReportSerializer(serializers.ModelSerializer):
    created_by_email = serializers.EmailField(source='created_by.email', read_only=True)
    
    class Meta:
        model = Report
        fields = [
            'id', 'name', 'report_number', 'report_type', 'description',
            'format', 'frequency', 'next_run', 'last_run', 'is_active',
            'created_by_email', 'created_at'
        ]

class ReportDetailSerializer(serializers.ModelSerializer):
    created_by_details = serializers.SerializerMethodField()
    
    class Meta:
        model = Report
        fields = '__all__'
    
    def get_created_by_details(self, obj):
        if obj.created_by:
            return {
                'email': obj.created_by.email,
                'name': obj.created_by.get_full_name()
            }
        return None

class DashboardSerializer(serializers.ModelSerializer):
    share_url = serializers.SerializerMethodField()
    
    class Meta:
        model = Dashboard
        fields = [
            'id', 'name', 'dashboard_type', 'widgets', 'layout',
            'filters', 'is_shared', 'share_url', 'created_at'
        ]
    
    def get_share_url(self, obj):
        if obj.is_shared:
            return f"/analytics/dashboard/shared/{obj.share_token}/"
        return None

class AnalyticsSummarySerializer(serializers.Serializer):
    """Serializer for analytics summary data"""
    total_users = serializers.IntegerField()
    active_today = serializers.IntegerField()
    total_bookings = serializers.IntegerField()
    total_revenue = serializers.DecimalField(max_digits=15, decimal_places=2)
    avg_booking_value = serializers.DecimalField(max_digits=10, decimal_places=2)
    conversion_rate = serializers.FloatField()
    bounce_rate = serializers.FloatField()

class RevenueReportSerializer(serializers.Serializer):
    """Serializer for revenue reports"""
    period = serializers.CharField()
    total_revenue = serializers.DecimalField(max_digits=15, decimal_places=2)
    by_payment_method = serializers.DictField()
    daily_breakdown = serializers.ListField()
    monthly_trend = serializers.ListField()

class FleetReportSerializer(serializers.Serializer):
    """Serializer for fleet utilization reports"""
    total_aircraft = serializers.IntegerField()
    utilization_rate = serializers.FloatField()
    flight_hours = serializers.DecimalField(max_digits=10, decimal_places=2)
    by_aircraft = serializers.ListField()
    maintenance_stats = serializers.DictField()