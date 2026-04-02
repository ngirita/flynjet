from celery import shared_task
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from .models import DailyMetric, Report, AnalyticsEvent
from .metrics import MetricsCalculator
from .reports import ReportGenerator, ScheduledReports
from .exports import ReportExporter
import logging

logger = logging.getLogger(__name__)

@shared_task
def calculate_daily_metrics():
    """Calculate metrics for yesterday"""
    yesterday = timezone.now().date() - timezone.timedelta(days=1)
    metric = MetricsCalculator.calculate_daily_metrics(yesterday)
    logger.info(f"Calculated daily metrics for {yesterday}")
    return metric.id if metric else None

@shared_task
def calculate_metrics_range(start_date, end_date):
    """Calculate metrics for date range"""
    metrics = MetricsCalculator.calculate_metrics_range(start_date, end_date)
    logger.info(f"Calculated metrics for {len(metrics)} days")
    return len(metrics)

@shared_task
def generate_daily_report():
    """Generate and send daily report"""
    yesterday = timezone.now().date() - timezone.timedelta(days=1)
    
    report_data = ReportGenerator.generate_revenue_report(yesterday, yesterday)
    
    # Send email to admins
    subject = f"Daily Report - {yesterday}"
    message = f"""
    Daily Revenue: ${report_data['summary']['total_revenue']}
    Bookings: {report_data['summary']['total_bookings']}
    Average Payment: ${report_data['summary']['avg_payment']}
    """
    
    from apps.accounts.models import User
    admin_emails = User.objects.filter(
        is_staff=True
    ).values_list('email', flat=True)
    
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        admin_emails,
        fail_silently=False,
    )
    
    logger.info(f"Daily report sent for {yesterday}")
    return True

@shared_task
def generate_weekly_report():
    """Generate weekly report"""
    end_date = timezone.now().date() - timezone.timedelta(days=1)
    start_date = end_date - timezone.timedelta(days=7)
    
    reports = {
        'revenue': ReportGenerator.generate_revenue_report(start_date, end_date),
        'bookings': ReportGenerator.generate_booking_report(start_date, end_date),
        'customer': ReportGenerator.generate_customer_report(start_date, end_date),
        'fleet': ReportGenerator.generate_fleet_report(start_date, end_date),
    }
    
    # Generate PDF and send
    pdf_content = ReportExporter.to_pdf(reports)
    
    # Save to file or send email
    logger.info(f"Weekly report generated for {start_date} to {end_date}")
    return True

@shared_task
def generate_monthly_report():
    """Generate monthly report"""
    end_date = timezone.now().date() - timezone.timedelta(days=1)
    start_date = end_date - timezone.timedelta(days=30)
    
    report = ReportGenerator.generate_revenue_report(start_date, end_date)
    
    # Store in database
    report_obj = Report.objects.create(
        name=f"Monthly Revenue Report {end_date.strftime('%B %Y')}",
        report_type='revenue',
        parameters={'start_date': str(start_date), 'end_date': str(end_date)},
        format='pdf'
    )
    
    report_obj.data = report
    report_obj.save()
    
    logger.info(f"Monthly report generated: {report_obj.id}")
    return report_obj.id

@shared_task
def run_scheduled_reports():
    """Run all scheduled reports"""
    count = ScheduledReports.run_scheduled_reports()
    logger.info(f"Ran {count} scheduled reports")
    return count

@shared_task
def cleanup_old_events(days=30):
    """Delete analytics events older than specified days"""
    cutoff = timezone.now() - timezone.timedelta(days=days)
    old_events = AnalyticsEvent.objects.filter(timestamp__lt=cutoff)
    
    count = old_events.count()
    old_events.delete()
    
    logger.info(f"Deleted {count} old analytics events")
    return count

@shared_task
def aggregate_hourly_metrics():
    """Aggregate metrics hourly for real-time dashboards"""
    now = timezone.now()
    hour_ago = now - timezone.timedelta(hours=1)
    
    # Count events in last hour
    events = AnalyticsEvent.objects.filter(timestamp__gte=hour_ago)
    
    metrics = {
        'timestamp': now.isoformat(),
        'page_views': events.filter(event_type='page_view').count(),
        'bookings': events.filter(event_type='booking_created').count(),
        'payments': events.filter(event_type='payment_completed').count(),
        'users': events.values('user').distinct().count(),
        'events_per_second': events.count() / 3600
    }
    
    # Store in cache for dashboard
    from django.core.cache import cache
    cache.set('realtime_metrics', metrics, timeout=3600)
    
    logger.info(f"Hourly metrics aggregated: {metrics}")
    return metrics

@shared_task
def detect_anomalies():
    """Detect anomalies in metrics"""
    today = timezone.now().date()
    yesterday = today - timezone.timedelta(days=1)
    last_week = today - timezone.timedelta(days=7)
    
    # Get metrics
    today_metric = DailyMetric.objects.filter(date=today).first()
    yesterday_metric = DailyMetric.objects.filter(date=yesterday).first()
    
    if not today_metric or not yesterday_metric:
        return None
    
    anomalies = []
    
    # Check for significant deviations
    metrics_to_check = ['revenue', 'total_bookings', 'new_users', 'page_views']
    
    for metric in metrics_to_check:
        today_val = getattr(today_metric, metric, 0) or 0
        yesterday_val = getattr(yesterday_metric, metric, 0) or 0
        
        if yesterday_val > 0:
            change_pct = ((today_val - yesterday_val) / yesterday_val) * 100
            
            if abs(change_pct) > 50:  # More than 50% change
                anomalies.append({
                    'metric': metric,
                    'today': float(today_val),
                    'yesterday': float(yesterday_val),
                    'change_pct': float(change_pct),
                    'severity': 'high' if abs(change_pct) > 100 else 'medium'
                })
    
    if anomalies:
        # Send alert
        send_mail(
            'Anomaly Detection Alert',
            f'Anomalies detected: {anomalies}',
            settings.DEFAULT_FROM_EMAIL,
            [settings.ADMIN_EMAIL],
            fail_silently=False,
        )
        
        logger.warning(f"Anomalies detected: {anomalies}")
    
    return anomalies

@shared_task
def generate_forecasts():
    """Generate forecasts for next period"""
    from .predictions import DemandForecaster
    
    bookings_forecast = DemandForecaster.forecast_bookings(30)
    revenue_forecast = DemandForecaster.forecast_revenue(30)
    
    # Store in cache
    from django.core.cache import cache
    cache.set('bookings_forecast', bookings_forecast, timeout=86400)
    cache.set('revenue_forecast', revenue_forecast, timeout=86400)
    
    logger.info("Forecasts generated")
    return {
        'bookings': len(bookings_forecast),
        'revenue': len(revenue_forecast)
    }