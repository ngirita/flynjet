import json
import csv
import uuid
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import ListView, DetailView, CreateView, TemplateView
from django.contrib import messages
from django.http import HttpResponse, JsonResponse, FileResponse
from django.utils import timezone
from django.urls import reverse_lazy
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Sum, Count, Avg
from django import forms
from .models import AnalyticsEvent, DailyMetric, Report, Dashboard
from .report_generators import ReportGenerator
from apps.bookings.models import Booking
from apps.payments.models import Payment

class AnalyticsDashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """Main analytics dashboard"""
    template_name = 'analytics/dashboard.html'
    
    def test_func(self):
        user = self.request.user
        return user.is_staff or user.user_type in ['admin', 'agent']
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get date range
        end_date = timezone.now().date()
        start_date = end_date - timezone.timedelta(days=30)
        
        # Get metrics
        metrics = DailyMetric.objects.filter(
            date__gte=start_date,
            date__lte=end_date
        ).order_by('date')
        
        # Calculate totals
        total_revenue = metrics.aggregate(Sum('revenue'))['revenue__sum'] or 0
        total_bookings = metrics.aggregate(Sum('total_bookings'))['total_bookings__sum'] or 0
        total_users = metrics.aggregate(Sum('new_users'))['new_users__sum'] or 0
        
        # Get user dashboards
        user_dashboards = Dashboard.objects.filter(user=self.request.user)
        
        context.update({
            'metrics': metrics,
            'total_revenue': total_revenue,
            'total_bookings': total_bookings,
            'total_users': total_users,
            'start_date': start_date,
            'end_date': end_date,
            'dashboards': user_dashboards,
            'chart_data': self.get_chart_data(metrics)
        })
        
        return context
    
    def get_chart_data(self, metrics):
        """Prepare chart data"""
        return {
            'labels': [m.date.strftime('%b %d') for m in metrics],
            'revenue': [float(m.revenue) for m in metrics],
            'bookings': [m.total_bookings for m in metrics],
            'users': [m.new_users for m in metrics]
        }


class ReportListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """List saved reports"""
    model = Report
    template_name = 'analytics/reports.html'
    context_object_name = 'reports'
    paginate_by = 20
    
    def test_func(self):
        user = self.request.user
        return user.is_staff or user.user_type in ['admin', 'agent']
    
    def get_queryset(self):
        return Report.objects.filter(created_by=self.request.user).order_by('-created_at')


class CreateReportView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """Create a new report"""
    model = Report
    template_name = 'analytics/create_report.html'
    fields = ['name', 'report_type', 'description', 'parameters', 'format', 'frequency']
    
    def test_func(self):
        user = self.request.user
        return user.is_staff or user.user_type in ['admin', 'agent']
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['parameters'].widget = forms.HiddenInput()
        return form
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['report_types'] = Report.REPORT_TYPES
        context['frequencies'] = Report.FREQUENCIES
        context['formats'] = Report.FORMATS
        return context
    
    def form_valid(self, form):
        form.instance.created_by = self.request.user
        response = super().form_valid(form)
        
        # Generate report immediately
        self.object.generate()
        
        messages.success(self.request, "Report created and generated successfully")
        return response
    
    def get_success_url(self):
        return reverse_lazy('analytics:report_detail', kwargs={'pk': self.object.pk})


class ReportDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """Report detail view"""
    model = Report
    template_name = 'analytics/report_detail.html'
    context_object_name = 'report'
    
    def test_func(self):
        report = self.get_object()
        return (self.request.user.is_staff or 
                self.request.user.user_type in ['admin'] or
                report.created_by == self.request.user)


def download_report(request, pk):
    """Download generated report"""
    report = get_object_or_404(Report, pk=pk)
    
    # Check permission
    if not (request.user.is_staff or report.created_by == request.user):
        messages.error(request, "Permission denied")
        return redirect('analytics:reports')
    
    if report.generated_file:
        return FileResponse(
            report.generated_file,
            as_attachment=True,
            filename=f"{report.name}.{report.format}"
        )
    
    messages.error(request, "Report file not found")
    return redirect('analytics:report_detail', pk=report.pk)


@csrf_exempt
def schedule_report(request, pk):
    """Schedule report generation"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    report = get_object_or_404(Report, pk=pk)
    
    # Check permission
    if not (request.user.is_staff or report.created_by == request.user):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    frequency = request.POST.get('frequency')
    if frequency in dict(Report.FREQUENCIES):
        report.frequency = frequency
        report.next_run = timezone.now()
        report.save()
        
        return JsonResponse({'status': 'scheduled', 'next_run': report.next_run})
    
    return JsonResponse({'error': 'Invalid frequency'}, status=400)


@csrf_exempt
def track_event(request):
    """Track analytics event (API endpoint)"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
        
        event = AnalyticsEvent.objects.create(
            event_id=str(uuid.uuid4()),
            event_type=data.get('event_type'),
            timestamp=timezone.now(),
            user=request.user if request.user.is_authenticated else None,
            anonymous_id=data.get('anonymous_id'),
            session_id=data.get('session_id'),
            url=data.get('url'),
            referrer=data.get('referrer'),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            ip_address=request.META.get('REMOTE_ADDR'),
            data=data.get('data', {})
        )
        
        return JsonResponse({'status': 'tracked', 'event_id': event.event_id})
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)