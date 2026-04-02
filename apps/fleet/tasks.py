from celery import shared_task
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from django.db import models
from django.db.models import Sum, Avg
from datetime import timedelta
from .models import Aircraft, AircraftMaintenance, AircraftDocument, FleetStats, AircraftCategory
import logging

logger = logging.getLogger(__name__)

@shared_task
def check_maintenance_schedules():
    """Check for upcoming and overdue maintenance"""
    today = timezone.now().date()
    
    # Check upcoming maintenance (next 7 days)
    upcoming = AircraftMaintenance.objects.filter(
        scheduled_start__date__gte=today,
        scheduled_start__date__lte=today + timedelta(days=7),
        status='scheduled'
    ).select_related('aircraft')
    
    for maintenance in upcoming:
        days_until = (maintenance.scheduled_start.date() - today).days
        send_maintenance_reminder.delay(maintenance.id, days_until)
        logger.info(f"Upcoming maintenance reminder sent for {maintenance.aircraft.registration_number}")
    
    # Check overdue maintenance
    overdue = AircraftMaintenance.objects.filter(
        scheduled_start__date__lt=today,
        status='scheduled'
    ).select_related('aircraft')
    
    for maintenance in overdue:
        send_maintenance_alert.delay(maintenance.id)
        logger.warning(f"Overdue maintenance alert for {maintenance.aircraft.registration_number}")
    
    return {
        'upcoming_count': upcoming.count(),
        'overdue_count': overdue.count()
    }

@shared_task
def send_maintenance_reminder(maintenance_id, days_until):
    """Send maintenance reminder email"""
    try:
        maintenance = AircraftMaintenance.objects.select_related('aircraft').get(id=maintenance_id)
        
        subject = f"Maintenance Reminder: {maintenance.aircraft.registration_number}"
        message = f"""
        Scheduled maintenance for aircraft {maintenance.aircraft.registration_number} is in {days_until} days.
        
        Maintenance: {maintenance.title}
        Type: {maintenance.get_maintenance_type_display()}
        Scheduled Start: {maintenance.scheduled_start}
        Location: {maintenance.maintenance_location}
        
        Please ensure all preparations are complete.
        """
        
        # Send to maintenance team
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [settings.MAINTENANCE_TEAM_EMAIL],
            fail_silently=False,
        )
        
        logger.info(f"Maintenance reminder sent for {maintenance.aircraft.registration_number}")
    except AircraftMaintenance.DoesNotExist:
        logger.error(f"Maintenance record {maintenance_id} not found")

@shared_task
def send_maintenance_alert(maintenance_id):
    """Send alert for overdue maintenance"""
    try:
        maintenance = AircraftMaintenance.objects.select_related('aircraft').get(id=maintenance_id)
        
        subject = f"URGENT: Overdue Maintenance - {maintenance.aircraft.registration_number}"
        message = f"""
        ALERT: Scheduled maintenance is overdue for aircraft {maintenance.aircraft.registration_number}.
        
        Maintenance: {maintenance.title}
        Scheduled Start: {maintenance.scheduled_start}
        Current Status: {maintenance.get_status_display()}
        
        Immediate action required.
        """
        
        # Send to management and maintenance team
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [settings.MANAGEMENT_EMAIL, settings.MAINTENANCE_TEAM_EMAIL],
            fail_silently=False,
        )
        
        logger.warning(f"Overdue maintenance alert sent for {maintenance.aircraft.registration_number}")
    except AircraftMaintenance.DoesNotExist:
        logger.error(f"Maintenance record {maintenance_id} not found")

@shared_task
def check_document_expirations():
    """Check for expiring documents"""
    today = timezone.now().date()
    thirty_days = today + timedelta(days=30)
    
    # Documents expiring in next 30 days
    expiring = AircraftDocument.objects.filter(
        expiry_date__lte=thirty_days,
        expiry_date__gte=today,
        is_approved=True
    ).select_related('aircraft')
    
    for document in expiring:
        days_left = (document.expiry_date - today).days
        send_document_expiry_notice.delay(document.id, days_left)
        logger.info(f"Document expiry notice sent for {document.aircraft.registration_number}")
    
    # Already expired documents
    expired = AircraftDocument.objects.filter(
        expiry_date__lt=today,
        is_approved=True
    ).select_related('aircraft')
    
    for document in expired:
        document.is_approved = False
        document.save()
        send_document_expired_alert.delay(document.id)
        logger.warning(f"Document expired alert for {document.aircraft.registration_number}")
    
    return {
        'expiring_count': expiring.count(),
        'expired_count': expired.count()
    }

@shared_task
def send_document_expiry_notice(document_id, days_left):
    """Send document expiry notice"""
    try:
        document = AircraftDocument.objects.select_related('aircraft').get(id=document_id)
        
        subject = f"Document Expiry Notice - {document.aircraft.registration_number}"
        message = f"""
        Document expiring in {days_left} days:
        
        Aircraft: {document.aircraft.registration_number}
        Document: {document.title}
        Type: {document.get_document_type_display()}
        Number: {document.document_number}
        Expiry Date: {document.expiry_date}
        
        Please renew as soon as possible.
        """
        
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [settings.DOCUMENTS_TEAM_EMAIL],
            fail_silently=False,
        )
        
        logger.info(f"Document expiry notice sent for {document.aircraft.registration_number}")
    except AircraftDocument.DoesNotExist:
        logger.error(f"Document {document_id} not found")

@shared_task
def send_document_expired_alert(document_id):
    """Send alert for expired document"""
    try:
        document = AircraftDocument.objects.select_related('aircraft').get(id=document_id)
        
        subject = f"EXPIRED DOCUMENT - {document.aircraft.registration_number}"
        message = f"""
        ALERT: Document has expired:
        
        Aircraft: {document.aircraft.registration_number}
        Document: {document.title}
        Type: {document.get_document_type_display()}
        Number: {document.document_number}
        Expiry Date: {document.expiry_date}
        
        This document is no longer valid. Immediate action required.
        """
        
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [settings.MANAGEMENT_EMAIL, settings.DOCUMENTS_TEAM_EMAIL],
            fail_silently=False,
        )
        
        logger.warning(f"Document expired alert sent for {document.aircraft.registration_number}")
    except AircraftDocument.DoesNotExist:
        logger.error(f"Document {document_id} not found")

@shared_task
def update_fleet_statistics():
    """Update fleet statistics daily"""
    today = timezone.now().date()
    
    stats, created = FleetStats.objects.get_or_create(date=today)
    
    stats.total_aircraft = Aircraft.objects.count()
    stats.available_aircraft = Aircraft.objects.filter(status='available').count()
    stats.in_maintenance = Aircraft.objects.filter(status='maintenance').count()
    stats.booked_aircraft = Aircraft.objects.filter(status='booked').count()
    
    # Calculate total flight hours
    total_hours = sum(a.total_flight_hours for a in Aircraft.objects.all())
    stats.total_flight_hours = total_hours
    
    # Calculate average utilization
    if stats.total_aircraft > 0:
        stats.average_utilization_rate = (stats.available_aircraft / stats.total_aircraft) * 100
    
    # Maintenance stats
    stats.scheduled_maintenance_count = AircraftMaintenance.objects.filter(
        scheduled_start__date=today
    ).count()
    
    stats.completed_maintenance_count = AircraftMaintenance.objects.filter(
        completed_at__date=today
    ).count()
    
    # Use Sum with proper import
    maintenance_cost = AircraftMaintenance.objects.filter(
        completed_at__date=today
    ).aggregate(total=models.Sum('actual_cost_usd'))['total']
    stats.maintenance_cost_usd = maintenance_cost or 0
    
    # Category breakdown
    category_breakdown = {}
    categories = AircraftCategory.objects.all()
    for category in categories:
        count = Aircraft.objects.filter(category=category).count()
        if count > 0:
            category_breakdown[category.name] = count
    
    stats.category_breakdown = category_breakdown
    stats.save()
    
    logger.info(f"Fleet statistics updated for {today}")
    return stats.id

@shared_task
def generate_maintenance_report():
    """Generate monthly maintenance report"""
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=30)
    
    maintenance = AircraftMaintenance.objects.filter(
        completed_at__date__gte=start_date,
        completed_at__date__lte=end_date
    )
    
    # Calculate by_type dictionary
    by_type = {}
    type_counts = maintenance.values_list('maintenance_type').annotate(count=models.Count('id'))
    for item in type_counts:
        by_type[item[0]] = item[1]
    
    total_cost = maintenance.aggregate(Sum('actual_cost_usd'))['actual_cost_usd__sum'] or 0
    average_cost = maintenance.aggregate(Avg('actual_cost_usd'))['actual_cost_usd__avg'] or 0
    
    # Calculate average downtime
    avg_downtime = None
    completed_maintenance = maintenance.filter(actual_start__isnull=False, actual_end__isnull=False)
    if completed_maintenance.exists():
        downtime_seconds = 0
        count = 0
        for m in completed_maintenance:
            if m.actual_start and m.actual_end:
                downtime_seconds += (m.actual_end - m.actual_start).total_seconds()
                count += 1
        if count > 0:
            avg_downtime = timedelta(seconds=downtime_seconds / count)
    
    report = {
        'period': f"{start_date} to {end_date}",
        'total_maintenance': maintenance.count(),
        'by_type': by_type,
        'total_cost': total_cost,
        'average_cost': average_cost,
        'average_downtime': str(avg_downtime) if avg_downtime else 'N/A',
    }
    
    # Send report to management
    send_mail(
        'Monthly Maintenance Report',
        f'Maintenance report for {start_date} to {end_date} is ready.\n\nReport: {report}',
        settings.DEFAULT_FROM_EMAIL,
        [settings.MANAGEMENT_EMAIL],
        fail_silently=False,
    )
    
    logger.info("Monthly maintenance report generated")
    return report