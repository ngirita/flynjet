from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model
from .models import AnalyticsEvent, DailyMetric, Report, Dashboard
from .metrics import MetricsCalculator
from .reports import ReportGenerator

User = get_user_model()

class AnalyticsModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
    
    def test_create_analytics_event(self):
        event = AnalyticsEvent.objects.create(
            event_id='test-event-123',
            event_type='page_view',
            user=self.user,
            session_id='test-session',
            url='/test/'
        )
        
        self.assertEqual(event.event_type, 'page_view')
        self.assertEqual(event.url, '/test/')
    
    def test_daily_metric(self):
        metric = DailyMetric.objects.create(
            date=timezone.now().date(),
            new_users=10,
            active_users=50,
            total_bookings=25,
            revenue=50000
        )
        
        self.assertEqual(metric.new_users, 10)
        self.assertEqual(metric.revenue, 50000)
    
    def test_create_report(self):
        report = Report.objects.create(
            name='Test Report',
            report_type='revenue',
            format='pdf',
            created_by=self.user
        )
        
        self.assertEqual(report.name, 'Test Report')
        self.assertEqual(report.report_number[:3], 'RPT')
    
    def test_create_dashboard(self):
        dashboard = Dashboard.objects.create(
            user=self.user,
            name='Test Dashboard',
            dashboard_type='personal'
        )
        
        self.assertEqual(dashboard.name, 'Test Dashboard')
        self.assertEqual(dashboard.dashboard_type, 'personal')

class AnalyticsMetricsTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
    
    def test_calculate_daily_metrics(self):
        date = timezone.now().date()
        metric = MetricsCalculator.calculate_daily_metrics(date)
        
        self.assertEqual(metric.date, date)
        self.assertIsNotNone(metric.id)
    
    def test_get_kpi_summary(self):
        summary = MetricsCalculator.get_kpi_summary()
        
        self.assertIn('today', summary)
        self.assertIn('vs_yesterday', summary)
        self.assertIn('weekly_avg', summary)

class AnalyticsViewsTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.client.login(email='test@example.com', password='testpass123')
    
    def test_dashboard_view(self):
        response = self.client.get(reverse('analytics:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'analytics/dashboard.html')
    
    def test_reports_list_view(self):
        response = self.client.get(reverse('analytics:reports'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'analytics/reports.html')