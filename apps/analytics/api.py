from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Sum, Count, Avg
from django.utils import timezone
from .models import AnalyticsEvent, DailyMetric, Report, Dashboard
from .serializers import (
    AnalyticsEventSerializer, DailyMetricSerializer,
    ReportSerializer, ReportDetailSerializer, DashboardSerializer
)

class AnalyticsEventViewSet(viewsets.ModelViewSet):
    """API for analytics events"""
    serializer_class = AnalyticsEventSerializer
    permission_classes = [permissions.IsAdminUser]
    queryset = AnalyticsEvent.objects.all().order_by('-timestamp')


class DailyMetricViewSet(viewsets.ReadOnlyModelViewSet):
    """API for daily metrics"""
    serializer_class = DailyMetricSerializer
    permission_classes = [permissions.IsAdminUser]
    queryset = DailyMetric.objects.all().order_by('-date')
    
    @action(detail=False, methods=['get'])
    def range(self, request):
        """Get metrics for date range"""
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        if not start_date or not end_date:
            return Response({'error': 'start_date and end_date required'}, status=400)
        
        metrics = DailyMetric.objects.filter(
            date__gte=start_date,
            date__lte=end_date
        ).order_by('date')
        
        serializer = self.get_serializer(metrics, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get summary metrics"""
        days = int(request.query_params.get('days', 30))
        start_date = timezone.now().date() - timezone.timedelta(days=days)
        
        metrics = DailyMetric.objects.filter(date__gte=start_date)
        
        summary = metrics.aggregate(
            total_revenue=Sum('revenue'),
            total_bookings=Sum('total_bookings'),
            avg_booking_value=Avg('average_booking_value'),
            total_users=Sum('new_users')
        )
        
        return Response(summary)


class ReportViewSet(viewsets.ModelViewSet):
    """API for reports"""
    permission_classes = [permissions.IsAdminUser]
    
    def get_queryset(self):
        return Report.objects.filter(created_by=self.request.user)
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ReportDetailSerializer
        return ReportSerializer
    
    def perform_create(self, serializer):
        report = serializer.save(created_by=self.request.user)
        report.generate()
    
    @action(detail=True, methods=['post'])
    def generate(self, request, pk=None):
        """Generate report"""
        report = self.get_object()
        report.generate()
        return Response({'status': 'generated'})


class DashboardViewSet(viewsets.ModelViewSet):
    """API for dashboards"""
    serializer_class = DashboardSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return Dashboard.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
    
    @action(detail=True, methods=['post'])
    def add_widget(self, request, pk=None):
        """Add widget to dashboard"""
        dashboard = self.get_object()
        widget_type = request.data.get('widget_type')
        config = request.data.get('config', {})
        
        widget = dashboard.add_widget(widget_type, config)
        return Response(widget)
    
    @action(detail=True, methods=['post'])
    def remove_widget(self, request, pk=None):
        """Remove widget from dashboard"""
        dashboard = self.get_object()
        widget_id = request.data.get('widget_id')
        
        dashboard.remove_widget(widget_id)
        return Response({'status': 'removed'})